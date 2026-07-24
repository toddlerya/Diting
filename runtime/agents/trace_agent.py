from typing import Any

from runtime.schema import BlackboardState
from runtime.tools.mcp_tools import query_trace_tool


def trace_node(state: BlackboardState) -> dict[str, Any]:
    entities = state.get("suspect_entities", ["system"])
    target = entities[0] if entities else "system"
    ev, msg = query_trace_tool(entity_id=target, trace_id="tr-88902")
    return {"evidences": [ev], "messages": [msg]}
