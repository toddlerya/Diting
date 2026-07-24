from typing import Any

from runtime.schema import BlackboardState
from runtime.tools.mcp_tools import query_knowledge_tool


def knowledge_node(state: BlackboardState) -> dict[str, Any]:
    ev, msg = query_knowledge_tool(query="High CPU load troubleshooting")
    runbook_dict = ev.details
    return {"evidences": [ev], "messages": [msg], "matched_runbooks": [runbook_dict]}
