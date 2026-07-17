import uuid
import random
from typing import Dict, List, Optional
from simulator.clock import SimulationClock
from simulator.event_bus import EventBus, BaseEvent
from simulator.entity import Entity, ServiceEntity, InfraEntity, Topology

class SpanNode:
    def __init__(self, span_id: str, parent_span_id: Optional[str], service: str):
        self.span_id = span_id
        self.parent_span_id = parent_span_id
        self.service = service
        self.status = "OK"
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

    def run_tick(self, ingress_qps: float, session_id: str = "default"):
        self.clock.tick()
        now = self.clock.now()
        tick = self.clock.current_tick
        
        # 1. 模拟生成请求与 Span 树骨架 (以 gateway 为入口)
        # 根据 QPS 决定本 Tick 处理的 Request 数量 (最少生成 1 个以供 TDD 验证)
        req_count = max(1, int(ingress_qps))
        
        for _ in range(req_count):
            trace_id = f"tr_{uuid.uuid4().hex[:8]}"
            root_span = self._build_span_tree("gateway", None)
            request = Request(trace_id, root_span)
            
            # 2. 模拟依赖判定与故障自底向上级联流转
            self._evaluate_span_node(root_span)
            
            # 3. 投递 Trace 结束事件发往总线，加入 session_id 以进行会话隔离
            self.bus.publish(BaseEvent(
                event_id=f"evt_{uuid.uuid4().hex[:8]}",
                tick=tick,
                timestamp=now,
                entity_id="gateway",
                severity="INFO",
                event_type="TraceFinishedEvent",
                payload={"session_id": session_id, "request": request}
            ))

    def _build_span_tree(self, service: str, parent_span_id: Optional[str]) -> SpanNode:
        span_id = f"sp_{uuid.uuid4().hex[:8]}"
        node = SpanNode(span_id, parent_span_id, service)
        
        node_config = self.topology.nodes.get(service, {})
        node_type = node_config.get("type", "fan_out")
        downstreams = self.topology.get_downstream_weights(service)
        
        if downstreams:
            if node_type == "fan_out":
                # 并行扇出：递归调用所有下游
                for down in downstreams.keys():
                    child = self._build_span_tree(down, span_id)
                    node.children.append(child)
            elif node_type == "route":
                # 路由选择：按权重进行加权随机游走，单次只走一条路径
                choices = list(downstreams.keys())
                weights = list(downstreams.values())
                chosen = random.choices(choices, weights=weights, k=1)[0]
                child = self._build_span_tree(chosen, span_id)
                node.children.append(child)
                
        return node

    def _evaluate_span_node(self, node: SpanNode):
        entity = self.entities.get(node.service)
        
        # 1. 递归判定子 Span 节点，自底向上流转
        # 在递归遍历子节点时，我们要处理上游节点的重试策略 (Retry Policy)
        if node.children:
            retry_policy = entity.resources.get("retry_policy") if entity else None
            max_attempts = retry_policy.get("max_attempts", 1) if retry_policy else 1
            
            resolved_children = []
            for child in list(node.children):
                self._evaluate_span_node(child)
                
                # 若子节点失败并且开启了重试
                if child.status != "OK" and max_attempts > 1:
                    attempts = [child]
                    success = False
                    
                    # 进行同层重试子节点的生成
                    for attempt_idx in range(1, max_attempts):
                        # 克隆/重新生成子节点，并标记 retry_count
                        retry_child = self._build_span_tree(child.service, node.span_id)
                        retry_child.retry_count = attempt_idx
                        self._evaluate_span_node(retry_child)
                        attempts.append(retry_child)
                        
                        if retry_child.status == "OK":
                            success = True
                            break
                            
                    resolved_children.extend(attempts)
                    if not success:
                        node.status = child.status  # 将最后的失败状态向上传播
                        node.error_message = f"Dependency {child.service} failed after {max_attempts} attempts"
                else:
                    resolved_children.append(child)
                    if child.status != "OK":
                        node.status = child.status
                        node.error_message = child.error_message
                        
            node.children = resolved_children

        # 2. 判定自身物理上限导致的故障状态码写入
        if entity:
            # 物理基础设施容量上限判断
            if isinstance(entity, InfraEntity):
                used = entity.resources.get("used", 0)
                capacity = entity.resources.get("capacity", 1)
                if used >= capacity:
                    node.status = "TIMEOUT"
                    node.error_message = f"{node.service} connection pool exhausted"
            
            # 微服务物理线程与连接池限制判断
            elif isinstance(entity, ServiceEntity):
                # 共享连接池在下游已被级联判断。这里也可以实现额外的线程和 heap 判定
                pass
