from typing import Any

from runtime.schema import BlackboardState
from runtime.tools.mcp_tools import query_knowledge_tool


def knowledge_node(state: BlackboardState) -> dict[str, Any]:
    ev, msg = query_knowledge_tool(query="High CPU load troubleshooting")
    runbook_info = {
        "runbook_id": ev.details.get("runbook_id", "RB-102"),
        "title": ev.details.get("title", "High CPU Recovery Procedure"),
    }
    return {
        "evidences": [ev],
        "messages": [msg],
        "matched_runbooks": [runbook_info],
    }
