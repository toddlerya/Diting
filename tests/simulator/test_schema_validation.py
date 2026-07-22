import pytest
from pydantic import ValidationError

from simulator.entity import InfraEntity, ServiceEntity
from simulator.environment import load_environment
from simulator.schema import (
    InfraResource,
    RetryPolicyConfig,
    ServiceResource,
)


def test_service_resource_validation():
    # 验证合法配置与强类型 Pydantic 表现
    res = ServiceResource(
        active_workers=5,
        max_workers=10,
        heap_used_mb=256.0,
        max_heap_mb=1024.0,
        request_queue_len=2,
        retry_policy=RetryPolicyConfig(max_attempts=3),
    )
    assert res.active_workers == 5
    assert res.max_workers == 10
    assert res.retry_policy is not None
    assert res.retry_policy.max_attempts == 3

    # 验证非法负数值被 Pydantic 拦截 (Fail-fast)
    with pytest.raises(ValidationError):
        ServiceResource(active_workers=-1)


def test_infra_resource_validation():
    res = InfraResource(used=10, capacity=100)
    assert res.used == 10
    assert res.capacity == 100

    # 验证属性修改
    res.used = 20
    assert res.used == 20


def test_entity_resource_auto_coercion():
    # 测试通过字典直接赋值给 entity.resources 自动由 setter 校验并转换为 Pydantic Model
    srv = ServiceEntity("order", "OrderService")
    srv.resources = {
        "active_workers": 4,
        "max_workers": 20,
        "heap_used_mb": 50.0,
        "max_heap_mb": 500.0,
    }
    assert isinstance(srv.resources, ServiceResource)
    assert srv.resources.active_workers == 4

    infra = InfraEntity("redis", "RedisPool")
    infra.resources = {"used": 5, "capacity": 50}
    assert isinstance(infra.resources, InfraResource)
    assert infra.resources.used == 5


def test_invalid_yaml_schema(tmp_path):
    # 构造非法 YAML 文件 (如 active_workers 为负数)
    invalid_yaml = tmp_path / "invalid_env.yaml"
    invalid_yaml.write_text(
        """
entities:
  order:
    class: "ServiceEntity"
    name: "OrderService"
    resources:
      active_workers: -5
      max_workers: 10
""",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_environment(str(invalid_yaml))
