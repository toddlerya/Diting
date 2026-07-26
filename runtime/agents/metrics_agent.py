from typing import Any

from runtime.agents.utils import get_target_entities
from runtime.schema import BlackboardState
from runtime.tools.mcp_tools import query_metrics_tool


def metrics_node(state: BlackboardState) -> dict[str, Any]:
    entities = get_target_entities(state)
    session_id = state.get("incident_alert", {}).get("session_id", "demo_session")
    evidences = []
    messages = []
    for target in entities:
        ev, msg = query_metrics_tool(
            entity_id=target,
            query="container_cpu_usage_seconds_total",
            session_id=session_id,
        )
        evidences.append(ev)
        messages.append(msg)
    return {"evidences": evidences, "messages": messages}
