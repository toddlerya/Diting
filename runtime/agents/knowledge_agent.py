from typing import Any

from runtime.schema import BlackboardState
from runtime.tools.mcp_tools import query_knowledge_tool


def knowledge_node(state: BlackboardState) -> dict[str, Any]:
    ev, msg = query_knowledge_tool(query="High CPU load troubleshooting")
    return {"evidences": [ev], "messages": [msg]}
