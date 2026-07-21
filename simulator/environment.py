import yaml
from pathlib import Path
from typing import Dict, Tuple
from simulator.entity import Entity, ServiceEntity, InfraEntity, Topology

def load_environment(filepath: str) -> Tuple[Dict[str, Entity], Topology]:
    """
    从指定 YAML 文件加载微服务拓扑和实体初始资源水位
    """
    path = Path(filepath).resolve()
    with path.open('r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}

    entities: Dict[str, Entity] = {}
    entities_data = data.get("entities", {})
    
    # 实例化各组件实体，并配置基础资源
    for entity_id, val in entities_data.items():
        cls_name = val.get("class", "ServiceEntity")
        name = val.get("name", entity_id)
        seed = val.get("seed", 42)
        
        if cls_name == "ServiceEntity":
            entity = ServiceEntity(entity_id, name, seed)
        elif cls_name == "InfraEntity":
            entity = InfraEntity(entity_id, name, seed)
        else:
            # 兜底策略：当显式指定为 "Entity" 或遇到未知的 class 类型时，降级退化为基类 Entity
            entity = Entity(entity_id, name, seed)
            
        entity.resources = val.get("resources", {})
        entities[entity_id] = entity

    # 构建调用拓扑图
    topo = Topology()
    topo_data = data.get("topology", {})
    for node_id, node_val in topo_data.items():
        node_type = node_val.get("type", "fan_out")
        topo.add_node(node_id, node_type)
        
        dependencies = node_val.get("dependencies", {})
        for dep_id, weight in dependencies.items():
            topo.add_dependency(node_id, dep_id, weight)

    return entities, topo
