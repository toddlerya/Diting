from langchain_core.messages import ToolMessage

from runtime.tools.mcp_tools import (
    query_knowledge_tool,
    query_logs_tool,
    query_metrics_tool,
    query_trace_tool,
)


def test_query_metrics_tool_mock():
    evidence, tool_msg = query_metrics_tool(
        entity_id="order-service",
        query="container_cpu_usage_seconds_total",
        tool_call_id="call_123",
    )
    assert evidence.source == "metric"
    assert evidence.entity_id == "order-service"
    assert isinstance(tool_msg, ToolMessage)
    assert tool_msg.tool_call_id == "call_123"


def test_query_logs_tool_mock():
    evidence, tool_msg = query_logs_tool(
        entity_id="order-service", query="Exception", tool_call_id="call_456"
    )
    assert evidence.source == "log"
    assert tool_msg.tool_call_id == "call_456"


def test_query_trace_tool_mock():
    evidence, tool_msg = query_trace_tool(
        entity_id="order-service", trace_id="tr-1002", tool_call_id="call_789"
    )
    assert evidence.source == "trace"
    assert tool_msg.tool_call_id == "call_789"


def test_query_knowledge_tool_mock():
    evidence, tool_msg = query_knowledge_tool(query="CPU Load Runbook", tool_call_id="call_999")
    assert evidence.source == "runbook"
    assert tool_msg.tool_call_id == "call_999"
