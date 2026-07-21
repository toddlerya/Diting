from typing import Any, Dict, Optional, Union
from pydantic import BaseModel, ConfigDict, Field


class RetryPolicyConfig(BaseModel):
    """服务重试策略配置。"""
    max_attempts: int = Field(default=1, ge=1, description="最大重试次数")


class BaseResource(BaseModel):
    """基础资源水位/容量模型。"""
    model_config = ConfigDict(extra="allow")


class ServiceResource(BaseResource):
    """微服务实体资源水位模型。"""
    active_workers: int = Field(default=0, ge=0, description="活跃工作线程数")
    max_workers: int = Field(default=1, ge=1, description="最大工作线程数")
    heap_used_mb: float = Field(default=0.0, ge=0.0, description="已用堆内存 (MB)")
    max_heap_mb: float = Field(default=1.0, gt=0.0, description="最大堆内存 (MB)")
    request_queue_len: int = Field(default=0, ge=0, description="请求等待队列长度")
    retry_policy: Optional[RetryPolicyConfig] = Field(default=None, description="服务重试策略")


class InfraResource(BaseResource):
    """基础设施实体资源容量模型。"""
    used: float = Field(default=0.0, ge=0.0, description="已使用资源量")
    capacity: float = Field(default=1.0, ge=0.0, description="资源总容量")


class EntityConfig(BaseModel):
    """环境 YAML 中的实体配置节点。"""
    class_name: str = Field(alias="class", default="ServiceEntity")
    name: Optional[str] = None
    seed: int = 42
    resources: Union[ServiceResource, InfraResource, Dict[str, Any]] = Field(default_factory=dict)


class TopologyNodeConfig(BaseModel):
    """环境 YAML 中的拓扑节点配置。"""
    type: str = "fan_out"
    dependencies: Dict[str, float] = Field(default_factory=dict)


class EnvironmentConfig(BaseModel):
    """环境配置文件 (default_env.yaml) 的整体 Schema。"""
    topology: Dict[str, TopologyNodeConfig] = Field(default_factory=dict)
    entities: Dict[str, EntityConfig] = Field(default_factory=dict)
