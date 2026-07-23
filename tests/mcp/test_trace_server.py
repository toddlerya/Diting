import httpx
import pytest
from mcp.state_client import StateClient
from mcp.trace_server import get_trace_tool, search_traces_tool


def test_trace_mcp_tools():
    mock_traces = [
        {
            "trace_id": "tr_001",
            "timestamp": "2026-07-23T00:00:00+00:00",
            "request": {
                "root_span": {
                    "service": "Gateway",
                    "duration": 600.0,
                    "status": "TIMEOUT",
                }
            },
        },
        {
            "trace_id": "tr_002",
            "timestamp": "2026-07-23T00:00:01+00:00",
            "request": {
                "root_span": {"service": "Gateway", "duration": 10.0, "status": "OK"}
            },
        },
    ]

    def handler(request: httpx.Request):
        if request.url.path == "/api/v1/traces":
            return httpx.Response(200, json=mock_traces)
        return httpx.Response(404)

    client = StateClient(transport=httpx.MockTransport(handler))

    # 验证按 trace_id 精确过滤
    tr = get_trace_tool("s1", "tr_001", client=client)
    assert tr is not None
    assert tr["trace_id"] == "tr_001"

    # 验证按 duration 过滤 slow traces
    slow = search_traces_tool("s1", min_duration_ms=500.0, client=client)
    assert len(slow) == 1
    assert slow[0]["trace_id"] == "tr_001"
