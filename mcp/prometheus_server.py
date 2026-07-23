from typing import Any, Dict, List, Optional
from mcp.server.fastmcp import FastMCP
from mcp.state_client import StateClient

mcp = FastMCP("Prometheus MCP Server")
_default_client = StateClient()


def query_range_tool(
    session_id: str,
    metric_name: str,
    start_tick: int = 0,
    end_tick: int = 100,
    client: Optional[StateClient] = None,
) -> List[Dict[str, Any]]:
    c = client or _default_client
    return c.get_metrics(session_id, metric_name, start_tick, end_tick)


def query_instant_tool(
    session_id: str, metric_name: str, client: Optional[StateClient] = None
) -> Dict[str, Any]:
    c = client or _default_client
    pts = c.get_metrics(session_id, metric_name, start_tick=0, end_tick=999999)
    if pts:
        return pts[-1]
    return {"timestamp": None, "value": None}


def list_metrics_tool(session_id: str, client: Optional[StateClient] = None) -> List[str]:
    c = client or _default_client
    pts = c.get_metrics(session_id, "*", start_tick=0, end_tick=999999)
    return list({p.get("metric_name", "") for p in pts if "metric_name" in p})


def get_alerts_tool(
    session_id: str, status: str = "firing", client: Optional[StateClient] = None
) -> List[Dict[str, Any]]:
    c = client or _default_client
    return c.get_alerts(session_id, status=status)


@mcp.tool()
def query_range(
    session_id: str, metric_name: str, start_tick: int = 0, end_tick: int = 100
) -> List[Dict[str, Any]]:
    """Query Prometheus range time-series metrics."""
    return query_range_tool(session_id, metric_name, start_tick, end_tick)


@mcp.tool()
def query_instant(session_id: str, metric_name: str) -> Dict[str, Any]:
    """Query Prometheus instant metric value snapshot."""
    return query_instant_tool(session_id, metric_name)


@mcp.tool()
def list_metrics(session_id: str) -> List[str]:
    """List available metric names recorded for current session."""
    return list_metrics_tool(session_id)


@mcp.tool()
def get_alerts(session_id: str, status: str = "firing") -> List[Dict[str, Any]]:
    """Query Alertmanager active firing or resolved alerts for the session."""
    return get_alerts_tool(session_id, status)


if __name__ == "__main__":
    mcp.run()
