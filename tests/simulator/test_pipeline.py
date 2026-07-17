from datetime import datetime, timezone
import pytest
from simulator.clock import SimulationClock
from simulator.event_bus import EventBus
from simulator.entity import ServiceEntity, InfraEntity, Topology
from simulator.pipeline import StateEvolutionPipeline

def test_pipeline_request_routing_and_retries():
    # 模拟拓扑: Gateway -> Order -> Payment (其中 Payment 遭遇故障，Order 触发重试)
    clock = SimulationClock(datetime(2026, 7, 17, 9, 0, 0, tzinfo=timezone.utc))
    bus = EventBus()
    
    gateway = ServiceEntity("gateway", "Gateway", seed=42)
    order = ServiceEntity("order", "OrderService", seed=42)
    payment = ServiceEntity("payment", "PaymentService", seed=42)
    redis = InfraEntity("redis", "RedisCache", seed=42)
    
    entities = {
        "gateway": gateway,
        "order": order,
        "payment": payment,
        "redis": redis
    }
    
    # 拓扑定义
    topo = Topology()
    topo.add_node("gateway", "fan_out")
    topo.add_dependency("gateway", "order", 1.0)
    
    topo.add_node("order", "route")
    topo.add_dependency("order", "payment", 1.0)
    
    topo.add_node("payment", "route")
    topo.add_dependency("payment", "redis", 1.0)
    
    # 初始化资源
    for entity in [gateway, order, payment]:
        entity.resources["active_workers"] = 2
        entity.resources["max_workers"] = 10
        entity.resources["heap_used_mb"] = 128
        entity.resources["max_heap_mb"] = 512
        entity.resources["request_queue_len"] = 0
        
    redis.resources["used"] = 10
    redis.resources["capacity"] = 50
    
    # 订阅 TraceFinishedEvent 收集最终 Trace
    finished_traces = []
    def trace_collector(event):
        finished_traces.append(event.payload["request"])
        
    bus.subscribe("TraceFinishedEvent", trace_collector)
    
    pipeline = StateEvolutionPipeline(entities, topo, clock, bus)
    
    # 1. 运行第一个正常 tick
    pipeline.run_tick(ingress_qps=1.0)
    assert len(finished_traces) == 1
    
    root_span = finished_traces[0].root_span
    assert root_span.service == "gateway"
    assert root_span.status == "OK"
    assert len(root_span.children) == 1
    assert root_span.children[0].service == "order"
    
    # 2. 注入 Redis 爆满故障，并配置 Order 针对 Payment 的 2 次重试策略
    redis.resources["used"] = 50 # 占满连接池，触发超时
    order.resources["retry_policy"] = {"max_attempts": 2}
    
    finished_traces.clear()
    # 运行第二个故障 tick
    pipeline.run_tick(ingress_qps=1.0)
    assert len(finished_traces) == 1
    
    fail_root = finished_traces[0].root_span
    # 检查重试 Span 是否以同层 children 的结构生成（即 order 下面拥有 2 个同层的 payment 尝试节点）
    order_span = fail_root.children[0]
    payment_attempts = [child for child in order_span.children if child.service == "payment"]
    
    # 应该尝试了 2 次 (max_attempts = 2)
    assert len(payment_attempts) == 2
    assert payment_attempts[0].status == "TIMEOUT"
    assert payment_attempts[1].status == "TIMEOUT"
    # Order 自身最终也标记为 ERROR 或 TIMEOUT
    assert order_span.status == "TIMEOUT"
