from typing import Any

from runtime.agents.utils import get_target_entities
from runtime.schema import BlackboardState
from runtime.tools.mcp_tools import query_logs_tool


def logs_node(state: BlackboardState) -> dict[str, Any]:
    entities = get_target_entities(state)
    evidences = []
    messages = []
    for target in entities:
        ev, msg = query_logs_tool(entity_id=target, query="Exception")
        evidences.append(ev)
        messages.append(msg)
    return {"evidences": evidences, "messages": messages}
