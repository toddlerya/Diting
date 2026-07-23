from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.state_client import StateClient

mcp = FastMCP("Prometheus MCP Server")
_default_client = StateClient()


def query_range_tool(
    session_id: str,
    metric_name: str,
    start_tick: int = 0,
    end_tick: int = 100,
    client: StateClient | None = None,
) -> list[dict[str, Any]]:
    c = client or _default_client
    return c.get_metrics(session_id, metric_name, start_tick, end_tick)


def query_instant_tool(
    session_id: str, metric_name: str, client: StateClient | None = None
) -> dict[str, Any]:
    c = client or _default_client
    pts = c.get_metrics(session_id, metric_name, start_tick=0, end_tick=999999)
    if pts:
        return pts[-1]
    return {"timestamp": None, "value": None}


def list_metrics_tool(session_id: str, client: StateClient | None = None) -> list[str]:
    c = client or _default_client
    return c.get_metric_names(session_id)


def get_alerts_tool(
    session_id: str, status: str = "firing", client: StateClient | None = None
) -> list[dict[str, Any]]:
    c = client or _default_client
    return c.get_alerts(session_id, status=status)


@mcp.tool()
def query_range(
    session_id: str, metric_name: str, start_tick: int = 0, end_tick: int = 100
) -> list[dict[str, Any]]:
    """Query Prometheus range time-series metrics."""
    return query_range_tool(session_id, metric_name, start_tick, end_tick)


@mcp.tool()
def query_instant(session_id: str, metric_name: str) -> dict[str, Any]:
    """Query Prometheus instant metric value snapshot."""
    return query_instant_tool(session_id, metric_name)


@mcp.tool()
def list_metrics(session_id: str) -> list[str]:
    """List available metric names recorded for current session."""
    return list_metrics_tool(session_id)


@mcp.tool()
def get_alerts(session_id: str, status: str = "firing") -> list[dict[str, Any]]:
    """Query Alertmanager active firing or resolved alerts for the session."""
    return get_alerts_tool(session_id, status)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Prometheus MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport mode (stdio/sse)",
    )
    parser.add_argument("--port", type=int, default=8001, help="Port for SSE server")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host for SSE server")
    args = parser.parse_args()

    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.run(transport=args.transport)
