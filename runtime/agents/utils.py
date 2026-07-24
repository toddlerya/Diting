from typing import Any

from runtime.schema import BlackboardState, Evidence


def get_target_entities(state: BlackboardState) -> list[str]:
    """提取白板中的 suspect_entities，默认为 ['system']。"""
    entities = state.get("suspect_entities", [])
    return entities if entities else ["system"]


def format_evidences_for_prompt(evidences: list[Evidence]) -> list[dict[str, Any]]:
    """序列化 Evidence 列表用于 Prompt 构建，自动过滤 details.raw 字段以防止 Context Bloat。"""
    formatted = []
    for ev in evidences:
        dump = ev.model_dump()
        if "details" in dump and isinstance(dump["details"], dict):
            dump["details"] = {k: v for k, v in dump["details"].items() if k != "raw"}
        formatted.append(dump)
    return formatted
