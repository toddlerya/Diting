import httpx
import pytest
from mcp.prometheus_server import get_alerts_tool, query_instant_tool, query_range_tool
from mcp.state_client import StateClient


def test_prometheus_mcp_tools():
    def handler(request: httpx.Request):
        if request.url.path == "/api/v1/metrics":
            return httpx.Response(
                200,
                json=[
                    {"timestamp": "2026-07-23T00:00:00+00:00", "value": 10.0},
                    {"timestamp": "2026-07-23T00:00:01+00:00", "value": 85.0},
                ],
            )
        elif request.url.path == "/api/v1/alerts":
            return httpx.Response(
                200, json=[{"status": "firing", "labels": {"alertname": "HighLatency"}}]
            )
        return httpx.Response(404)

    client = StateClient(transport=httpx.MockTransport(handler))
    range_res = query_range_tool("s1", "gateway_cpu_usage", client=client)
    assert len(range_res) == 2

    instant_res = query_instant_tool("s1", "gateway_cpu_usage", client=client)
    assert instant_res["value"] == 85.0

    alerts_res = get_alerts_tool("s1", "firing", client=client)
    assert len(alerts_res) == 1
    assert alerts_res[0]["labels"]["alertname"] == "HighLatency"
