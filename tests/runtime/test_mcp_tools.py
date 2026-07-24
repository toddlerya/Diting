from langchain_core.messages import ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient

from runtime.tools.mcp_tools import (
    get_mcp_client,
    load_all_mcp_tools,
    query_knowledge_tool,
    query_logs_tool,
    query_metrics_tool,
    query_trace_tool,
)


def test_query_metrics_tool():
    evidence, tool_msg = query_metrics_tool(
        entity_id="order-service",
        query="container_cpu_usage_seconds_total",
        tool_call_id="call_123",
    )
    assert evidence.source == "metric"
    assert evidence.entity_id == "order-service"
    assert isinstance(tool_msg, ToolMessage)
    assert tool_msg.tool_call_id == "call_123"


def test_query_logs_tool():
    evidence, tool_msg = query_logs_tool(
        entity_id="order-service", query="Exception", tool_call_id="call_456"
    )
    assert evidence.source == "log"
    assert evidence.entity_id == "order-service"
    assert isinstance(tool_msg, ToolMessage)
    assert tool_msg.tool_call_id == "call_456"


def test_query_trace_tool():
    evidence, tool_msg = query_trace_tool(
        entity_id="order-service", trace_id="tr-1002", tool_call_id="call_789"
    )
    assert evidence.source == "trace"
    assert evidence.entity_id == "order-service"
    assert isinstance(tool_msg, ToolMessage)
    assert tool_msg.tool_call_id == "call_789"


def test_query_knowledge_tool():
    evidence, tool_msg = query_knowledge_tool(query="CPU Load Runbook", tool_call_id="call_999")
    assert evidence.source == "runbook"
    assert evidence.entity_id == "system"
    assert isinstance(tool_msg, ToolMessage)
    assert tool_msg.tool_call_id == "call_999"


def test_get_mcp_client_and_load_tools():
    import asyncio

    client = get_mcp_client()
    assert isinstance(client, MultiServerMCPClient)
    tools = asyncio.run(load_all_mcp_tools(client))
    assert len(tools) > 0
    tool_names = {t.name for t in tools}
    assert (
        "query_instant" in tool_names
        or "query_logs" in tool_names
        or "search_runbooks" in tool_names
    )


def test_mcp_fallback_on_unreachable_server():
    # 测试指定无效地址端口时的优雅降级逻辑
    invalid_client = get_mcp_client(
        {
            "invalid_prometheus": {
                "url": "http://127.0.0.1:59999/mcp",
                "transport": "streamable-http",
            }
        }
    )
    evidence, tool_msg = query_metrics_tool(
        entity_id="fallback-service",
        query="cpu_usage",
        client=invalid_client,
        tool_call_id="call_fallback",
    )
    assert evidence.source == "metric"
    assert evidence.entity_id == "fallback-service"
    assert tool_msg.tool_call_id == "call_fallback"
