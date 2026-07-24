from typing import Any

from runtime.schema import BlackboardState
from runtime.tools.mcp_tools import query_logs_tool


def logs_node(state: BlackboardState) -> dict[str, Any]:
    entities = state.get("suspect_entities", ["system"])
    target = entities[0] if entities else "system"
    ev, msg = query_logs_tool(entity_id=target, query="Exception")
    return {"evidences": [ev], "messages": [msg]}
