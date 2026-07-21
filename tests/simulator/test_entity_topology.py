import pytest
from simulator.entity import ServiceEntity, InfraEntity, Topology

def test_topology_routing_and_fanout():
    topo = Topology()
    # Gateway 是并行扇出
    topo.add_node("Gateway", "fan_out")
    topo.add_dependency("Gateway", "OrderService", 1.0)
    topo.add_dependency("Gateway", "UserService", 1.0)
    
    # OrderService 是加权随机路由
    topo.add_node("OrderService", "route")
    topo.add_dependency("OrderService", "PaymentService", 0.8)
    topo.add_dependency("OrderService", "InventoryService", 0.2)
    
    assert topo.nodes["Gateway"]["type"] == "fan_out"
    assert topo.nodes["OrderService"]["type"] == "route"
    assert topo.get_downstream_weights("OrderService")["PaymentService"] == 0.8

def test_derived_metrics_with_noise_determinism():
    # 两个使用相同 Seed 实例化的 Service，其派生指标应该 100% 相同 (确定性)
    srv1 = ServiceEntity("pay1", "Payment1", seed=42)
    srv2 = ServiceEntity("pay2", "Payment2", seed=42)
    
    # 初始化物理资源状态
    for srv in [srv1, srv2]:
        srv.resources.active_workers = 5
        srv.resources.max_workers = 10
        srv.resources.heap_used_mb = 256
        srv.resources.max_heap_mb = 512
        srv.resources.request_queue_len = 0
        
    metrics1 = srv1.derived_metrics()
    metrics2 = srv2.derived_metrics()
    
    assert "cpu_usage" in metrics1
    assert "latency" in metrics1
    assert metrics1["cpu_usage"] == metrics2["cpu_usage"]
    assert metrics1["latency"] == metrics2["latency"]


def test_topology_validation():
    # 1. 空拓扑校验
    topo = Topology()
    with pytest.raises(ValueError, match="仿真拓扑结构为空"):
        topo.validate()

    # 2. 正常 DAG 拓扑校验
    topo.add_node("Gateway", "fan_out")
    topo.add_dependency("Gateway", "OrderService", 1.0)
    topo.validate()  # 应该不报错

    # 3. 循环拓扑校验
    topo.add_dependency("OrderService", "Gateway", 1.0)
    with pytest.raises(ValueError, match="仿真拓扑结构中存在循环调用"):
        topo.validate()

