from simulator.entity import InfraEntity, ServiceEntity
from simulator.environment import load_environment


def test_load_environment(tmp_path):
    env_content = """
topology:
  gateway:
    type: "fan_out"
    dependencies:
      order: 1.0
  order:
    type: "route"
    dependencies:
      redis: 1.0

entities:
  gateway:
    class: "ServiceEntity"
    name: "Gateway"
    seed: 10
    resources:
      active_workers: 5
      max_workers: 20
  redis:
    class: "InfraEntity"
    name: "RedisPool"
    seed: 20
    resources:
      used: 2
      capacity: 10
"""

    env_file = tmp_path / "test_env.yaml"
    env_file.write_text(env_content)

    # 加载测试环境
    entities, topo = load_environment(str(env_file))

    # 验证 entities 成功创建
    assert "gateway" in entities
    assert "redis" in entities

    gateway = entities["gateway"]
    redis = entities["redis"]

    # 校验类映射
    assert isinstance(gateway, ServiceEntity)
    assert isinstance(redis, InfraEntity)

    # 校验属性与资源参数
    assert gateway.name == "Gateway"
    assert gateway.resources.active_workers == 5
    assert gateway.resources.max_workers == 20

    assert redis.name == "RedisPool"
    assert redis.resources.used == 2
    assert redis.resources.capacity == 10

    # 验证 Topology 成功组装
    assert "gateway" in topo.nodes
    assert topo.nodes["gateway"]["type"] == "fan_out"

    assert "order" in topo.nodes
    assert topo.nodes["order"]["type"] == "route"

    # 验证拓扑依赖
    gateway_deps = topo.get_downstream_weights("gateway")
    assert gateway_deps == {"order": 1.0}

    order_deps = topo.get_downstream_weights("order")
    assert order_deps == {"redis": 1.0}
