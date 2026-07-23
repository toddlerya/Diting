import httpx
import pytest

from mcp.state_client import StateClient


def test_state_client_success():
    def handler(request: httpx.Request):
        if request.url.path == "/api/v1/metrics":
            return httpx.Response(
                200, json=[{"timestamp": "2026-07-23T00:00:00+00:00", "value": 42.0}]
            )
        elif request.url.path == "/api/v1/session":
            return httpx.Response(200, json={"status": "cleared", "session_id": "s1"})
        elif request.url.path == "/api/v1/logs":
            return httpx.Response(200, json=["log1"])
        elif request.url.path == "/api/v1/traces":
            return httpx.Response(200, json=[{"trace_id": "t1"}])
        elif request.url.path == "/api/v1/alerts":
            return httpx.Response(200, json=[{"status": "firing"}])
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = StateClient(transport=transport)

    metrics = client.get_metrics("s1", "cpu_usage", 0, 10)
    assert len(metrics) == 1
    assert metrics[0]["value"] == 42.0

    logs = client.get_logs("s1", "PaymentService", "ERROR")
    assert logs == ["log1"]

    traces = client.get_traces("s1")
    assert len(traces) == 1

    alerts = client.get_alerts("s1", "firing")
    assert len(alerts) == 1

    del_res = client.delete_session("s1")
    assert del_res["status"] == "cleared"


def test_state_client_unreachable_fail_fast():
    def handler(request: httpx.Request):
        raise httpx.ConnectError("Connection refused")

    transport = httpx.MockTransport(handler)
    client = StateClient(transport=transport)
    with pytest.raises(RuntimeError, match="State Server not reachable"):
        client.get_metrics("s1", "cpu_usage", 0, 10)
