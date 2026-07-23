import httpx
import pytest
from mcp.loki_server import list_services_tool, query_logs_tool
from mcp.state_client import StateClient


def test_loki_mcp_query_logs():
    def handler(request: httpx.Request):
        if request.url.path == "/api/v1/logs":
            return httpx.Response(
                200,
                json=[
                    "[2026-07-23T00:00:00+00:00] [ERROR] [trace_id: tr_123] PaymentService: Failed due to Redis timeout"
                ],
            )
        return httpx.Response(404)

    client = StateClient(transport=httpx.MockTransport(handler))
    logs = query_logs_tool("s1", "PaymentService", "ERROR", client=client)
    assert len(logs) == 1
    assert "Redis timeout" in logs[0]

    services = list_services_tool("s1", client=client)
    assert "PaymentService" in services
