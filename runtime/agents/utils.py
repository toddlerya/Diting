from runtime.schema import BlackboardState


def get_target_entities(state: BlackboardState) -> list[str]:
    """提取白板中的 suspect_entities，默认为 ['system']。"""
    entities = state.get("suspect_entities", [])
    return entities if entities else ["system"]
