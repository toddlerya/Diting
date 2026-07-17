import random
from typing import Dict, Optional, List

class Entity:
    def __init__(self, entity_id: str, name: str, seed: int = 42):
        self.entity_id = entity_id
        self.name = name
        self.resources: Dict[str, float] = {}
        # 实例化局部伪随机生成器以实现完全确定性的白噪声
        self.random_gen = random.Random(seed)

    def derived_metrics(self) -> Dict[str, float]:
        return {}

class ServiceEntity(Entity):
    def derived_metrics(self) -> Dict[str, float]:
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
    def derived_metrics(self) -> Dict[str, float]:
        used = self.resources.get("used", 0)
        capacity = self.resources.get("capacity", 1)
        util = (used / capacity) * 100
        return {
            "utilization": util
        }

class Topology:
    def __init__(self):
        self.nodes: Dict[str, dict] = {}
        self.edges: Dict[str, Dict[str, float]] = {}
        
    def add_node(self, entity_id: str, node_type: str = "fan_out"):
        # node_type 支持 'fan_out' (并行扇出) 或 'route' (随机路由游走)
        self.nodes[entity_id] = {"type": node_type}
        if entity_id not in self.edges:
            self.edges[entity_id] = {}
            
    def add_dependency(self, upstream: str, downstream: str, weight: float):
        if upstream not in self.edges:
            self.edges[upstream] = {}
        self.edges[upstream][downstream] = weight
        if upstream not in self.nodes:
            self.nodes[upstream] = {"type": "fan_out"} # 默认并行扇出
            
    def get_downstream_weights(self, entity_id: str) -> Dict[str, float]:
        return self.edges.get(entity_id, {})
