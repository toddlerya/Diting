from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.state_client import StateClient

mcp = FastMCP("Trace MCP Server")
_default_client = StateClient()


def get_trace_tool(
    session_id: str, trace_id: str, client: StateClient | None = None
) -> dict[str, Any] | None:
    c = client or _default_client
    traces = c.get_traces(session_id)
    for tr in traces:
        if tr.get("trace_id") == trace_id:
            return tr
    return None


def search_traces_tool(
    session_id: str, min_duration_ms: float = 0.0, client: StateClient | None = None
) -> list[dict[str, Any]]:
    c = client or _default_client
    traces = c.get_traces(session_id)
    results = []
    for tr in traces:
        root_span = tr.get("request", {}).get("root_span", {})
        duration = root_span.get("duration", 0.0)
        if duration >= min_duration_ms:
            results.append(tr)
    return results


@mcp.tool()
def get_trace(session_id: str, trace_id: str) -> dict[str, Any] | None:
    """Get detailed trace span tree by trace_id."""
    return get_trace_tool(session_id, trace_id)


@mcp.tool()
def search_traces(session_id: str, min_duration_ms: float = 0.0) -> list[dict[str, Any]]:
    """Search slow traces exceeding min_duration_ms threshold."""
    return search_traces_tool(session_id, min_duration_ms)


if __name__ == "__main__":
    mcp.run()
