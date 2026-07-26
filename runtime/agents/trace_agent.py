from typing import Any

from runtime.agents.utils import get_target_entities
from runtime.schema import BlackboardState
from runtime.tools.mcp_tools import query_trace_tool


def trace_node(state: BlackboardState) -> dict[str, Any]:
    entities = get_target_entities(state)
    alert = state.get("incident_alert", {})
    trace_id = alert.get("trace_id", "tr-88902")
    session_id = alert.get("session_id", "demo_session")
    evidences = []
    messages = []
    for target in entities:
        ev, msg = query_trace_tool(
            entity_id=target,
            trace_id=trace_id,
            session_id=session_id,
        )
        evidences.append(ev)
        messages.append(msg)
    return {"evidences": evidences, "messages": messages}
