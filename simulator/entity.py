import random
from typing import Dict, Optional, List

class Entity:
    """
    仿真实体基类。
    用于代表仿真系统中的各种物理或逻辑组件（如服务、数据库等），并持有其基础资源指标。
    """
    def __init__(self, entity_id: str, name: str, seed: int = 42):
        """
        初始化实体。

        Args:
            entity_id (str): 实体的唯一标识。
            name (str): 实体的易读名称。
            seed (int, optional): 局部随机数生成器的种子，用于保持噪声可复现。默认为 42。
        """
        self.entity_id = entity_id
        self.name = name
        self.resources: Dict[str, float] = {}
        # 实例化局部伪随机生成器以实现完全确定性的白噪声
        self.random_gen = random.Random(seed)

    def derived_metrics(self) -> Dict[str, float]:
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
    def derived_metrics(self) -> Dict[str, float]:
        """
        计算并返回微服务的派生监控指标（CPU 使用率、服务响应延迟、错误率等）。

        计算逻辑：
        1. cpu_usage：通过工作线程使用率、堆内存占用率、请求队列长度综合计算，并加入白噪声。
        2. latency：主要由请求队列等待长度决定。

        Returns:
            Dict[str, float]: 包含 'cpu_usage'、'latency' 和 'error_rate' 的字典。
        """
        active_workers = self.resources.get("active_workers", 0)
        max_workers = self.resources.get("max_workers", 1)
        heap_used = self.resources.get("heap_used_mb", 0)
        max_heap = self.resources.get("max_heap_mb", 1)
        queue_len = self.resources.get("request_queue_len", 0)
        
        # 物理衍生公式计算 CPU (带白噪声)
        base_cpu = (active_workers / max_workers) * 80 + (heap_used / max_heap) * 15 + queue_len * 2
        noise = self.random_gen.uniform(-2.0, 2.0)
        cpu = max(0.0, min(100.0, base_cpu + noise))
        
        # 物理衍生公式计算 Latency (ms)
        base_latency = 5.0 + queue_len * 20.0
        
        return {
            "cpu_usage": cpu,
            "latency": base_latency,
            "error_rate": 0.0
        }

class InfraEntity(Entity):
    """
    基础设施实体。
    模拟诸如 Redis 缓存池、数据库连接池等底层资源，可计算资源利用率指标。
    """
    def derived_metrics(self) -> Dict[str, float]:
        """
        计算并返回基础设施的利用率指标。

        Returns:
            Dict[str, float]: 包含 'utilization' 的字典。
        """
        used = self.resources.get("used", 0)
        capacity = self.resources.get("capacity", 1)
        util = (used / capacity) * 100
        return {
            "utilization": util
        }

class Topology:
    """
    系统拓扑结构。
    用于管理服务实体之间的调用网络和依赖权重，并决定请求在服务之间的传播方式。
    """
    def __init__(self):
        """初始化拓扑结构，构建空节点表和空依赖边表。"""
        self.nodes: Dict[str, dict] = {}
        self.edges: Dict[str, Dict[str, float]] = {}
        
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
            self.nodes[upstream] = {"type": "fan_out"} # 默认并行扇出
            
    def get_downstream_weights(self, entity_id: str) -> Dict[str, float]:
        """
        获取指定实体的所有下游依赖服务及对应的调用权重。

        Args:
            entity_id (str): 当前实体 ID。

        Returns:
            Dict[str, float]: 下游依赖服务 ID 及其权重的映射。
        """
        return self.edges.get(entity_id, {})
