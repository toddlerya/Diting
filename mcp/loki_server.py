from mcp.server.fastmcp import FastMCP
from mcp.state_client import StateClient

mcp = FastMCP("Loki MCP Server")
_default_client = StateClient()


def query_logs_tool(
    session_id: str, service: str, level: str = "ERROR", client: StateClient | None = None
) -> list[str]:
    c = client or _default_client
    return c.get_logs(session_id, service, level)


def list_services_tool(session_id: str, client: StateClient | None = None) -> list[str]:
    c = client or _default_client
    logs = c.get_logs(session_id, service="*", level="*")
    services = set()
    for log in logs:
        parts = log.split(" ")
        for part in parts:
            if part.endswith(":"):
                srv = part.rstrip(":").strip()
                if srv and not srv.startswith("["):
                    services.add(srv)
    return list(services)


@mcp.tool()
def query_logs(session_id: str, service: str, level: str = "ERROR") -> list[str]:
    """Query Loki logs for a specific service and severity level."""
    return query_logs_tool(session_id, service, level)


@mcp.tool()
def list_services(session_id: str) -> list[str]:
    """List services that have recorded logs in the session."""
    return list_services_tool(session_id)


if __name__ == "__main__":
    mcp.run()
