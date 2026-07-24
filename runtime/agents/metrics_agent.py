from typing import Any

from runtime.schema import BlackboardState
from runtime.tools.mcp_tools import query_metrics_tool


def metrics_node(state: BlackboardState) -> dict[str, Any]:
    entities = state.get("suspect_entities", ["system"])
    target = entities[0] if entities else "system"
    ev, msg = query_metrics_tool(entity_id=target, query="container_cpu_usage_seconds_total")
    return {"evidences": [ev], "messages": [msg]}
