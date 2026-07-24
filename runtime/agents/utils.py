from typing import Any

from runtime.schema import BlackboardState, Evidence


def get_target_entities(state: BlackboardState) -> list[str]:
    """提取白板中的 suspect_entities，默认为 ['system']。"""
    entities = state.get("suspect_entities", [])
    return entities if entities else ["system"]


def format_evidences_for_prompt(evidences: list[Evidence]) -> list[dict[str, Any]]:
    """序列化 Evidence 列表用于 Prompt 构建，自动过滤 details.raw 字段以防止 Context Bloat。

    保留 `is_fallback` 标记字段，让下游 Synthesizer 能区分真实证据与 MCP 不可达时的兜底伪证据，
    避免把 fallback 数据当成物理事实纳入根因判定。
    """
    formatted = []
    for ev in evidences:
        dump = ev.model_dump()
        if "details" in dump and isinstance(dump["details"], dict):
            dump["details"] = {k: v for k, v in dump["details"].items() if k != "raw"}
        if "is_fallback" not in dump:
            dump["is_fallback"] = bool(dump.get("details", {}).get("is_fallback", False))
        formatted.append(dump)
    return formatted


def has_fallback_evidence(evidences: list[Evidence]) -> bool:
    """判断证据集中是否包含 MCP 不可达时生成的 fallback 伪证据。"""
    return any(ev.details.get("is_fallback", False) for ev in evidences)
