import random

from pydantic import BaseModel

from simulator.schema import BaseResource, InfraResource, ServiceResource


class Entity:
    """
    仿真实体基类。
    用于代表仿真系统中的各种物理或逻辑组件（如服务、数据库等），并持有其基础资源指标。
    """

    def __init__(
        self,
        entity_id: str,
        name: str,
        seed: int = 42,
        resources: BaseResource | dict | None = None,
    ):
        """
        初始化实体。

        Args:
            entity_id (str): 实体的唯一标识。
            name (str): 实体的易读名称。
            seed (int, optional): 局部随机数生成器的种子，用于保持噪声可复现。默认为 42。
            resources (Optional[Union[BaseResource, Dict]]): 实体基础资源模型。
        """
        self.entity_id = entity_id
        self.name = name
        self._resources: BaseResource = BaseResource()
        self.random_gen = random.Random(seed)
        if resources is not None:
            self.resources = resources

    @property
    def resources(self) -> BaseResource:
        return self._resources

    @resources.setter
    def resources(self, val: BaseResource | dict):
        if isinstance(val, BaseResource):
            self._resources = val
        elif isinstance(val, dict):
            self._resources = BaseResource.model_validate(val)
        else:
            self._resources = val

    def derived_metrics(self) -> dict[str, float]:
        """
        根据底层资源计算并返回派生监控指标。
        基类提供空实现，子类应重写以返回特定的指标。

        Returns:
            Dict[str, float]: 派生指标的字典（如 CPU 使用率、响应延迟等）。
        """
        return {}


class ServiceEntity(Entity):
    """
    微服务实体。
    模拟一个运行的微服务实例，可根据资源消耗计算服务的 CPU 使用率、请求延迟等衍生指标。
    """

    def __init__(
        self,
        entity_id: str,
        name: str,
        seed: int = 42,
        resources: ServiceResource | dict | None = None,
    ):
        super().__init__(entity_id, name, seed, resources)
        self.last_error_rate: float = 0.0
        if not isinstance(self._resources, ServiceResource):
            if isinstance(self._resources, BaseModel):
                self._resources = ServiceResource.model_validate(self._resources.model_dump())
            elif isinstance(self._resources, dict):
                self._resources = ServiceResource.model_validate(self._resources)
            else:
                self._resources = ServiceResource()

    @property
    def resources(self) -> ServiceResource:
        return self._resources  # type: ignore

    @resources.setter
    def resources(self, val: ServiceResource | dict):
        if isinstance(val, ServiceResource):
            self._resources = val
        elif isinstance(val, dict):
            self._resources = ServiceResource.model_validate(val)
        else:
            self._resources = val

    def derived_metrics(self) -> dict[str, float]:
        """
        计算并返回微服务的派生监控指标（CPU 使用率、服务响应延迟、错误率等）。

        计算逻辑：
        1. cpu_usage：通过工作线程使用率、堆内存占用率、请求队列长度综合计算，并加入白噪声。
        2. latency：主要由请求队列等待长度决定。
        3. error_rate：由管道（Pipeline）推演统计的当前 Tick 实际错误率。

        Returns:
            Dict[str, float]: 包含 'cpu_usage'、'latency' 和 'error_rate' 的字典。
        """
        res = self.resources
        active_workers = res.active_workers
        max_workers = res.max_workers if res.max_workers > 0 else 1
        heap_used = res.heap_used_mb
        max_heap = res.max_heap_mb if res.max_heap_mb > 0 else 1.0
        queue_len = res.request_queue_len

        # 物理衍生公式计算 CPU (带白噪声)
        base_cpu = (active_workers / max_workers) * 80 + (heap_used / max_heap) * 15 + queue_len * 2
        noise = self.random_gen.uniform(-2.0, 2.0)
        cpu = max(0.0, min(100.0, base_cpu + noise))

        # 物理衍生公式计算 Latency (ms)
        base_latency = 5.0 + queue_len * 20.0

        return {"cpu_usage": cpu, "latency": base_latency, "error_rate": self.last_error_rate}


class InfraEntity(Entity):
    """
    基础设施实体。
    模拟诸如 Redis 缓存池、数据库连接池等底层资源，可计算资源利用率指标。
    """

    def __init__(
        self,
        entity_id: str,
        name: str,
        seed: int = 42,
        resources: InfraResource | dict | None = None,
    ):
        super().__init__(entity_id, name, seed, resources)
        if not isinstance(self._resources, InfraResource):
            if isinstance(self._resources, BaseModel):
                self._resources = InfraResource.model_validate(self._resources.model_dump())
            elif isinstance(self._resources, dict):
                self._resources = InfraResource.model_validate(self._resources)
            else:
                self._resources = InfraResource()

    @property
    def resources(self) -> InfraResource:
        return self._resources  # type: ignore

    @resources.setter
    def resources(self, val: InfraResource | dict):
        if isinstance(val, InfraResource):
            self._resources = val
        elif isinstance(val, dict):
            self._resources = InfraResource.model_validate(val)
        else:
            self._resources = val

    def derived_metrics(self) -> dict[str, float]:
        """
        计算并返回基础设施的利用率指标。

        Returns:
            Dict[str, float]: 包含 'utilization' 的字典。
        """
        res = self.resources
        used = res.used
        capacity = res.capacity if res.capacity > 0 else 1.0
        util = (used / capacity) * 100
        return {"utilization": util}


class Topology:
    """
    系统拓扑结构。
    用于管理服务实体之间的调用网络和依赖权重，并决定请求在服务之间的传播方式。
    """

    def __init__(self):
        """初始化拓扑结构，构建空节点表和空依赖边表。"""
        self.nodes: dict[str, dict] = {}
        self.edges: dict[str, dict[str, float]] = {}

    def add_node(self, entity_id: str, node_type: str = "fan_out"):
        """
        添加一个拓扑节点（实体）。

        Args:
            entity_id (str): 实体的唯一标识。
            node_type (str, optional): 节点类型，支持 'fan_out' (并行扇出) 或 'route' (随机路由)。默认为 "fan_out"。
        """
        # node_type 支持 'fan_out' (并行扇出) 或 'route' (随机路由游走)
        self.nodes[entity_id] = {"type": node_type}
        if entity_id not in self.edges:
            self.edges[entity_id] = {}

    def add_dependency(self, upstream: str, downstream: str, weight: float):
        """
        添加一条服务调用依赖边。

        Args:
            upstream (str): 上游服务实体 ID。
            downstream (str): 下游依赖服务实体 ID。
            weight (float): 调用的权重/比例。
        """
        if upstream not in self.edges:
            self.edges[upstream] = {}
        self.edges[upstream][downstream] = weight
        if upstream not in self.nodes:
            self.nodes[upstream] = {"type": "fan_out"}  # 默认并行扇出

    def get_downstream_weights(self, entity_id: str) -> dict[str, float]:
        """
        获取指定实体的所有下游依赖服务及对应的调用权重。

        Args:
            entity_id (str): 当前实体 ID。

        Returns:
            Dict[str, float]: 下游依赖服务 ID 及其权重的映射。
        """
        return self.edges.get(entity_id, {})

    def validate(self):
        """
        验证拓扑结构的合法性，必须是非空的有向无环图 (DAG)。

        Raises:
            ValueError: 如果拓扑为空或存在循环依赖（环路）。
        """
        if not self.nodes:
            raise ValueError("仿真拓扑结构为空，无法进行仿真推演，请先配置拓扑节点！")

        # 使用 DFS 进行有向图的环路检测
        visited = {}  # 0: 未访问, 1: 正在访问, 2: 已完成访问

        def has_cycle(node: str) -> bool:
            visited[node] = 1
            downstreams = self.get_downstream_weights(node).keys()
            for down in downstreams:
                state = visited.get(down, 0)
                if state == 1:
                    return True  # 发现回边，说明有环
                elif state == 0:
                    if has_cycle(down):
                        return True
            visited[node] = 2
            return False

        for node in self.nodes:
            if visited.get(node, 0) == 0:
                if has_cycle(node):
                    raise ValueError(
                        "仿真拓扑结构中存在循环调用（环路），必须为有向无环图（DAG）！"
                    )
