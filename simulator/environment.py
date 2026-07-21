import yaml
from pathlib import Path
from typing import Dict, Tuple
from simulator.entity import Entity, ServiceEntity, InfraEntity, Topology
from simulator.schema import EnvironmentConfig, ServiceResource, InfraResource, BaseResource

def load_environment(filepath: str) -> Tuple[Dict[str, Entity], Topology]:
    """
    从指定 YAML 文件加载微服务拓扑和实体初始资源水位，并通过 Pydantic 校验 Schema 合法性。
    """
    path = Path(filepath).resolve()
    with path.open('r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}

    # 1. 通过 Pydantic 校验并构建环境配置 Schema
    env_config = EnvironmentConfig.model_validate(data)

    entities: Dict[str, Entity] = {}
    
    # 2. 实例化各组件实体，并配置基础资源
    for entity_id, entity_cfg in env_config.entities.items():
        cls_name = entity_cfg.class_name
        name = entity_cfg.name if entity_cfg.name is not None else entity_id
        seed = entity_cfg.seed
        res_data = entity_cfg.resources

        if cls_name == "ServiceEntity":
            if isinstance(res_data, ServiceResource):
                res_obj = res_data
            elif isinstance(res_data, dict):
                res_obj = ServiceResource.model_validate(res_data)
            else:
                res_obj = ServiceResource.model_validate(res_data.model_dump())
            entity = ServiceEntity(entity_id, name, seed, resources=res_obj)
        elif cls_name == "InfraEntity":
            if isinstance(res_data, InfraResource):
                res_obj = res_data
            elif isinstance(res_data, dict):
                res_obj = InfraResource.model_validate(res_data)
            else:
                res_obj = InfraResource.model_validate(res_data.model_dump())
            entity = InfraEntity(entity_id, name, seed, resources=res_obj)
        else:
            if isinstance(res_data, BaseResource):
                res_obj = res_data
            elif isinstance(res_data, dict):
                res_obj = BaseResource.model_validate(res_data)
            else:
                res_obj = BaseResource.model_validate(res_data.model_dump())
            entity = Entity(entity_id, name, seed, resources=res_obj)
            
        entities[entity_id] = entity

    # 3. 构建调用拓扑图
    topo = Topology()
    for node_id, node_cfg in env_config.topology.items():
        topo.add_node(node_id, node_cfg.type)
        
        for dep_id, weight in node_cfg.dependencies.items():
            topo.add_dependency(node_id, dep_id, weight)

    return entities, topo
