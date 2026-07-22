import random
import uuid
from enum import Enum
from typing import Dict, List, Optional

from simulator.clock import SimulationClock
from simulator.entity import Entity, InfraEntity, ServiceEntity, Topology
from simulator.event_bus import BaseEvent, EventBus, EventType, EventSeverity


class SpanStatus(str, Enum):
    """
    Span 节点的状态枚举。
    继承 str 以保证与标准字符串比较及序列化的兼容性。
    """
    OK = "OK"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"


class SpanNode:
    def __init__(self, span_id: str, parent_span_id: Optional[str], service: str):
        self.span_id = span_id
        self.parent_span_id = parent_span_id
        self.service = service
        self.status = SpanStatus.OK
        self.duration = 0.0
        self.retry_count = 0
        self.error_message = ""
        self.children: List['SpanNode'] = []

class Request:
    def __init__(self, trace_id: str, root_span: SpanNode):
        self.trace_id = trace_id
        self.root_span = root_span

class StateEvolutionPipeline:
    def __init__(self, entities: Dict[str, Entity], topology: Topology,
                 clock: SimulationClock, bus: EventBus):
        self.entities = entities
        self.topology = topology
        self.clock = clock
        self.bus = bus
        self.topology.validate()

    def _find_entry_point(self) -> str:
        """
        寻找拓扑中入度为 0 的节点作为入口服务。
        因为初始化时已校验拓扑为 DAG，因此必然存在至少一个入度为 0 的节点。
        """
        # 收集所有下游节点 ID
        all_downstreams = set()
        for downstreams in self.topology.edges.values():
            all_downstreams.update(downstreams.keys())

        # 查找所有入度为 0 的节点
        entry_points = [node for node in self.topology.nodes if node not in all_downstreams]

        # 优先匹配常用的网关命名，否则默认选择第一个入口
        for name in ["gateway", "api-gateway"]:
            if name in entry_points:
                return name
        return entry_points[0]

    def run_tick(self, ingress_qps: float, session_id: str = "default"):
        self.clock.tick()
        now = self.clock.now()
        tick = self.clock.current_tick

        # 动态获取当前拓扑的入口服务节点
        entry_point = self._find_entry_point()

        # 1. 模拟生成请求与 Span 树骨架 (以 entry_point 为入口)
        # 根据 QPS 决定本 Tick 处理的 Request 数量 (最少生成 1 个以供 TDD 验证)
        req_count = max(1, int(ingress_qps))

        for _ in range(req_count):
            trace_id = f"tr_{uuid.uuid4().hex[:8]}"
            root_span = self._build_span_tree(entry_point, None)
            request = Request(trace_id, root_span)

            # 2. 模拟依赖判定与故障自底向上级联流转
            self._evaluate_span_node(root_span)

            # 3. 投递 Trace 结束事件发往总线，加入 session_id 以进行会话隔离
            self.bus.publish(BaseEvent(
                event_id=f"evt_{uuid.uuid4().hex[:8]}",
                tick=tick,
                timestamp=now,
                entity_id=entry_point,
                severity=EventSeverity.INFO,
                event_type=EventType.TRACE_FINISHED,
                payload={"session_id": session_id, "request": request}
            ))

    def _build_span_tree(self, service: str, parent_span_id: Optional[str]) -> SpanNode:
        """
        根据拓扑依赖图递归构建调用的 Span 树结构骨架。

        根据服务的节点类型 (fan_out 或 route) 决定如何向下游扩散请求：
        1. fan_out (并行扇出): 同时递归调用所有的下游依赖服务（如微服务同时查数据库与缓存）。
        2. route (加权随机路由): 根据下游权重随机选择其中一条路径调用（如 A/B 测试、网关路由等），
           优先使用实体持有的 PRNG 伪随机生成器以保证仿真推演完全可复现。

        Args:
            service (str): 当前调用的服务实体 ID。
            parent_span_id (Optional[str]): 父级 Span 的 ID（根节点入口为 None）。

        Returns:
            SpanNode: 构建完成的当前服务 Span 节点及其嵌套子节点树。
        """
        # 1. 生成唯一的 Span ID 并创建节点
        span_id = f"sp_{uuid.uuid4().hex[:8]}"
        node = SpanNode(span_id, parent_span_id, service)

        # 2. 查询拓扑中该服务的配置类型和下游依赖项
        node_config = self.topology.nodes.get(service, {})
        node_type = node_config.get("type", "fan_out")
        downstreams = self.topology.get_downstream_weights(service)

        # 3. 如果存在下游依赖，按节点类型递归构建子 Span 树
        if downstreams:
            if node_type == "fan_out":
                # 并行扇出模式：递归调用所有下游服务
                for down in downstreams.keys():
                    child = self._build_span_tree(down, span_id)
                    node.children.append(child)
            elif node_type == "route":
                # 路由选择模式：按权重进行加权随机游走，单次请求只走一条路径
                choices = list(downstreams.keys())
                weights = list(downstreams.values())
                # 优先使用父节点实体的局部 PRNG，确保基于 Seed 的完全重现确定性
                parent_entity = self.entities.get(service)
                if parent_entity:
                    chosen = parent_entity.random_gen.choices(choices, weights=weights, k=1)[0]
                else:
                    chosen = random.choices(choices, weights=weights, k=1)[0]
                child = self._build_span_tree(chosen, span_id)
                node.children.append(child)

        return node

    def _evaluate_span_node(self, node: SpanNode):
        """
        评估 Span 节点的健康状态、物理资源上限判定、重试机制以及故障自底向上的级联传播。

        评估逻辑：
        1. 节点自检 (资源上限判定):
           - InfraEntity (如 Redis/DB 连接池): 若当前使用量 >= 最大容量，标记为 TIMEOUT 超时。
           - ServiceEntity (微服务实例): 
             - 若工作线程数 >= 最大线程数，标记为 TIMEOUT (线程池耗尽)。
             - 若堆内存使用 >= 最大堆内存，标记为 ERROR (内存溢出 OOM)。

        2. 递归评估子 Span & 重试策略 (自底向上级联):
           - 递归评估各个子 Span 节点的健康状态。
           - 如果子 Span 调用失败（非 OK），且当前服务配置了重试策略 (max_attempts > 1)：
             - 重新构建该下游服务的 Span 子树并重试推演，记录同层重试次数 (retry_count)。
             - 若某次重试成功，则恢复链路；若所有重试均失败，则将最终失败状态向上传播给当前父节点。
           - 如果未开启重试，直接将下游子节点的失败状态与错误信息向上传播给当前父节点。

        Args:
            node (SpanNode): 待评估的 Span 节点。
        """
        entity = self.entities.get(node.service)
        if not entity:
            return

        # 1. 物理上限判定 (工作线程耗尽, OOM, 或 Infra 资源满)
        if isinstance(entity, InfraEntity):
            used = entity.resources.used
            capacity = entity.resources.capacity
            if capacity > 0 and used >= capacity:
                node.status = SpanStatus.TIMEOUT
                node.error_message = f"{entity.name} resource capacity exhausted ({used}/{capacity})"
        elif isinstance(entity, ServiceEntity):
            res = entity.resources
            active_workers = res.active_workers
            max_workers = res.max_workers
            heap_used = res.heap_used_mb
            max_heap = res.max_heap_mb

            if active_workers >= max_workers:
                node.status = SpanStatus.TIMEOUT
                node.error_message = f"{entity.name} thread pool exhausted ({active_workers}/{max_workers})"
            elif heap_used >= max_heap:
                node.status = SpanStatus.ERROR
                node.error_message = f"{entity.name} Out Of Memory (OOM) ({heap_used}MB/{max_heap}MB)"

        # 2. 递归判定子 Span 节点，自底向上流转并处理重试
        if node.children:
            retry_policy = getattr(entity.resources, "retry_policy", None) if entity else None
            if isinstance(retry_policy, dict):
                max_attempts = retry_policy.get("max_attempts", 1)
            elif retry_policy is not None:
                max_attempts = getattr(retry_policy, "max_attempts", 1)
            else:
                max_attempts = 1

            resolved_children = []
            for child in list(node.children):
                # 先递归评估子节点自身的健康状态
                self._evaluate_span_node(child)

                # 若子节点调用失败，并且当前服务开启了重试策略 (max_attempts > 1)
                if child.status != SpanStatus.OK and max_attempts > 1:
                    attempts = [child]
                    success = False

                    # 进行同层重试子节点的生成与推演
                    for attempt_idx in range(1, max_attempts):
                        retry_child = self._build_span_tree(child.service, node.span_id)
                        retry_child.retry_count = attempt_idx
                        self._evaluate_span_node(retry_child)
                        attempts.append(retry_child)

                        if retry_child.status == SpanStatus.OK:
                            success = True
                            break

                    resolved_children.extend(attempts)
                    if not success:
                        # 达到最大重试次数后仍全部失败，将失败状态向父节点传播
                        node.status = child.status
                        node.error_message = f"Dependency {child.service} failed after {max_attempts} attempts"
                else:
                    resolved_children.append(child)
                    # 未开启重试时，直接将下游子节点的失败状态向父节点传播
                    if child.status != SpanStatus.OK:
                        node.status = child.status
                        node.error_message = child.error_message

            node.children = resolved_children

