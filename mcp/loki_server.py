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
    return c.get_log_services(session_id)


@mcp.tool()
def query_logs(session_id: str, service: str, level: str = "ERROR") -> list[str]:
    """Query Loki logs for a specific service and severity level."""
    return query_logs_tool(session_id, service, level)


@mcp.tool()
def list_services(session_id: str) -> list[str]:
    """List services that have recorded logs in the session."""
    return list_services_tool(session_id)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Loki MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport mode (stdio/sse)",
    )
    parser.add_argument("--port", type=int, default=8002, help="Port for SSE server")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host for SSE server")
    args = parser.parse_args()

    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.run(transport=args.transport)
