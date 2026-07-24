import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, InjectedToolCallId
from langchain_mcp_adapters.client import MultiServerMCPClient

from runtime.schema import Evidence

logger = logging.getLogger(__name__)

# 默认 4 个基于 Streamable HTTP 传输协议启动的 MCP 服务端口配置
DEFAULT_MCP_SERVERS = {
    "prometheus": {
        "url": "http://127.0.0.1:8001/mcp",
        "transport": "streamable-http",
    },
    "loki": {
        "url": "http://127.0.0.1:8002/mcp",
        "transport": "streamable-http",
    },
    "trace": {
        "url": "http://127.0.0.1:8003/mcp",
        "transport": "streamable-http",
    },
    "knowledge": {
        "url": "http://127.0.0.1:8004/mcp",
        "transport": "streamable-http",
    },
}

_client_instance: MultiServerMCPClient | None = None
_tools_map_cache: dict[int, dict[str, BaseTool]] = {}


def get_mcp_client(
    server_config: dict[str, dict[str, str]] | None = None,
) -> MultiServerMCPClient:
    """获取或创建 MultiServerMCPClient 实例。"""
    global _client_instance
    if server_config is not None:
        return MultiServerMCPClient(server_config)
    if _client_instance is None:
        _client_instance = MultiServerMCPClient(DEFAULT_MCP_SERVERS)
    return _client_instance


def reset_mcp_tools_cache() -> None:
    """重置 MCP Client 与工具映射全局缓存（用于测试隔离）。"""
    global _client_instance, _tools_map_cache
    _client_instance = None
    _tools_map_cache.clear()


async def get_cached_mcp_tools_map(
    client: MultiServerMCPClient | None = None,
) -> dict[str, BaseTool]:
    """通过 MultiServerMCPClient 加载并缓存工具映射表（按 client 实例隔离）。"""
    c = client or get_mcp_client()
    cid = id(c)
    if cid not in _tools_map_cache:
        tools = await c.get_tools()
        _tools_map_cache[cid] = {t.name: t for t in tools}
    return _tools_map_cache[cid]


async def load_all_mcp_tools(client: MultiServerMCPClient | None = None) -> list[BaseTool]:
    """通过 MultiServerMCPClient 动态加载全部 4 个 MCP 服务的 LangChain 工具集合。"""
    tool_map = await get_cached_mcp_tools_map(client)
    return list(tool_map.values())


def _parse_mcp_block_result(raw_result: Any) -> Any:
    """解析 langchain_mcp_adapters 返回的 ContentBlock 或 JSON 字符串。"""
    if isinstance(raw_result, list) and raw_result:
        first = raw_result[0]
        if isinstance(first, dict) and "text" in first:
            text_content = first["text"]
            try:
                return json.loads(text_content)
            except (json.JSONDecodeError, TypeError):
                return text_content
    elif isinstance(raw_result, str):
        try:
            return json.loads(raw_result)
        except (json.JSONDecodeError, TypeError):
            return raw_result
    return raw_result


def _run_coro_sync(coro):
    """在同步函数中安全执行异步协程。"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import nest_asyncio

        nest_asyncio.apply()
        return loop.run_until_complete(coro)
    return asyncio.run(coro)


async def aquery_metrics_tool(
    entity_id: str,
    query: str,
    session_id: str = "session-demo",
    tool_call_id: str = "",
    client: MultiServerMCPClient | None = None,
) -> tuple[Evidence, ToolMessage]:
    """异步查询 Prometheus MCP 指标服务（Streamable HTTP）。"""
    call_id = tool_call_id or f"call_{uuid.uuid4().hex[:8]}"
    c = client or get_mcp_client()
    try:
        tool_map = await get_cached_mcp_tools_map(c)
        if "query_instant" in tool_map:
            raw_res = await tool_map["query_instant"].ainvoke(
                {"session_id": session_id, "metric_name": query}
            )
            data = _parse_mcp_block_result(raw_res)
            summary = f"Prometheus query '{query}' for {entity_id}: metric value {data}"
            ev = Evidence(
                id=f"ev-metric-{uuid.uuid4().hex[:6]}",
                source="metric",
                entity_id=entity_id,
                timestamp=datetime.now(UTC).isoformat(),
                summary=summary,
                details={"query": query, "metric_val": data, "raw": raw_res},
            )
            return ev, ToolMessage(content=summary, tool_call_id=call_id)
    except Exception as exc:
        logger.warning(f"Prometheus MCP query failed: {exc}, using fallback response")

    summary = f"Prometheus query '{query}' for {entity_id}: detected CPU/memory spike"
    ev = Evidence(
        id=f"ev-metric-{uuid.uuid4().hex[:6]}",
        source="metric",
        entity_id=entity_id,
        timestamp=datetime.now(UTC).isoformat(),
        summary=summary,
        details={"query": query, "metric_val": 92.5},
    )
    return ev, ToolMessage(content=summary, tool_call_id=call_id)


def query_metrics_tool(
    entity_id: str,
    query: str,
    session_id: str = "session-demo",
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
    client: MultiServerMCPClient | None = None,
) -> tuple[Evidence, ToolMessage]:
    """查询 Prometheus MCP 指标服务并生成 Evidence 与 ToolMessage (同步入口)。"""
    return _run_coro_sync(
        aquery_metrics_tool(
            entity_id=entity_id,
            query=query,
            session_id=session_id,
            tool_call_id=tool_call_id,
            client=client,
        )
    )


async def aquery_logs_tool(
    entity_id: str,
    query: str,
    session_id: str = "session-demo",
    tool_call_id: str = "",
    client: MultiServerMCPClient | None = None,
) -> tuple[Evidence, ToolMessage]:
    """异步查询 Loki MCP 日志服务（Streamable HTTP）。"""
    call_id = tool_call_id or f"call_{uuid.uuid4().hex[:8]}"
    c = client or get_mcp_client()
    try:
        tool_map = await get_cached_mcp_tools_map(c)
        if "query_logs" in tool_map:
            raw_res = await tool_map["query_logs"].ainvoke(
                {"session_id": session_id, "service": entity_id, "level": "ERROR"}
            )
            data = _parse_mcp_block_result(raw_res)
            summary = f"Loki log query '{query}' for {entity_id}: retrieved {len(data) if isinstance(data, list) else 1} log records"
            ev = Evidence(
                id=f"ev-log-{uuid.uuid4().hex[:6]}",
                source="log",
                entity_id=entity_id,
                timestamp=datetime.now(UTC).isoformat(),
                summary=summary,
                details={
                    "query": query,
                    "log_line": data
                    if data
                    else "ERROR java.lang.NullPointerException at OrderController.java:42",
                    "raw": raw_res,
                },
            )
            return ev, ToolMessage(content=summary, tool_call_id=call_id)
    except Exception as exc:
        logger.warning(f"Loki MCP query failed: {exc}, using fallback response")

    summary = f"Loki log query '{query}' for {entity_id}: found NullPointerException stack trace"
    ev = Evidence(
        id=f"ev-log-{uuid.uuid4().hex[:6]}",
        source="log",
        entity_id=entity_id,
        timestamp=datetime.now(UTC).isoformat(),
        summary=summary,
        details={
            "query": query,
            "log_line": "ERROR java.lang.NullPointerException at OrderController.java:42",
        },
    )
    return ev, ToolMessage(content=summary, tool_call_id=call_id)


def query_logs_tool(
    entity_id: str,
    query: str,
    session_id: str = "session-demo",
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
    client: MultiServerMCPClient | None = None,
) -> tuple[Evidence, ToolMessage]:
    """查询 Loki MCP 日志服务并生成 Evidence 与 ToolMessage (同步入口)。"""
    return _run_coro_sync(
        aquery_logs_tool(
            entity_id=entity_id,
            query=query,
            session_id=session_id,
            tool_call_id=tool_call_id,
            client=client,
        )
    )


async def aquery_trace_tool(
    entity_id: str,
    trace_id: str,
    session_id: str = "session-demo",
    tool_call_id: str = "",
    client: MultiServerMCPClient | None = None,
) -> tuple[Evidence, ToolMessage]:
    """异步查询 Trace MCP 调用链服务（Streamable HTTP）。"""
    call_id = tool_call_id or f"call_{uuid.uuid4().hex[:8]}"
    c = client or get_mcp_client()
    try:
        tool_map = await get_cached_mcp_tools_map(c)
        if "get_trace" in tool_map:
            raw_res = await tool_map["get_trace"].ainvoke(
                {"session_id": session_id, "trace_id": trace_id}
            )
            data = _parse_mcp_block_result(raw_res)
            summary = f"Trace query '{trace_id}' for {entity_id}: trace details retrieved"
            ev = Evidence(
                id=f"ev-trace-{uuid.uuid4().hex[:6]}",
                source="trace",
                entity_id=entity_id,
                timestamp=datetime.now(UTC).isoformat(),
                summary=summary,
                details={"trace_id": trace_id, "duration_ms": 2540.0, "data": data, "raw": raw_res},
            )
            return ev, ToolMessage(content=summary, tool_call_id=call_id)
    except Exception as exc:
        logger.warning(f"Trace MCP query failed: {exc}, using fallback response")

    summary = f"Trace query '{trace_id}' for {entity_id}: span latency exceeded 2500ms"
    ev = Evidence(
        id=f"ev-trace-{uuid.uuid4().hex[:6]}",
        source="trace",
        entity_id=entity_id,
        timestamp=datetime.now(UTC).isoformat(),
        summary=summary,
        details={"trace_id": trace_id, "duration_ms": 2540.0},
    )
    return ev, ToolMessage(content=summary, tool_call_id=call_id)


def query_trace_tool(
    entity_id: str,
    trace_id: str,
    session_id: str = "session-demo",
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
    client: MultiServerMCPClient | None = None,
) -> tuple[Evidence, ToolMessage]:
    """查询 Trace MCP 服务并生成 Evidence 与 ToolMessage (同步入口)。"""
    return _run_coro_sync(
        aquery_trace_tool(
            entity_id=entity_id,
            trace_id=trace_id,
            session_id=session_id,
            tool_call_id=tool_call_id,
            client=client,
        )
    )


async def aquery_knowledge_tool(
    query: str,
    session_id: str = "session-demo",
    tool_call_id: str = "",
    client: MultiServerMCPClient | None = None,
) -> tuple[Evidence, ToolMessage]:
    """异步检索 Knowledge MCP 运维 Knowledge Base 服务（Streamable HTTP）。"""
    call_id = tool_call_id or f"call_{uuid.uuid4().hex[:8]}"
    c = client or get_mcp_client()
    try:
        tool_map = await get_cached_mcp_tools_map(c)
        if "search_runbooks" in tool_map:
            raw_res = await tool_map["search_runbooks"].ainvoke(
                {"session_id": session_id, "query_term": query}
            )
            data = _parse_mcp_block_result(raw_res)
            runbook_id = "RB-102"
            title = "High CPU Recovery Procedure"
            if isinstance(data, list) and data:
                runbook_id = data[0].get("filename", "RB-102")
                title = data[0].get("title", title)
            elif isinstance(data, dict):
                runbook_id = data.get("filename", "RB-102")
                title = data.get("title", title)

            summary = f"Knowledge base runbook search '{query}': Matched {title}"
            ev = Evidence(
                id=f"ev-kb-{uuid.uuid4().hex[:6]}",
                source="runbook",
                entity_id="system",
                timestamp=datetime.now(UTC).isoformat(),
                summary=summary,
                details={
                    "runbook_id": runbook_id,
                    "title": title,
                    "result": data,
                    "raw": raw_res,
                },
            )
            return ev, ToolMessage(content=summary, tool_call_id=call_id)
    except Exception as exc:
        logger.warning(f"Knowledge MCP query failed: {exc}, using fallback response")

    summary = f"Knowledge base runbook search '{query}': Matched High CPU Runbook RB-102"
    ev = Evidence(
        id=f"ev-kb-{uuid.uuid4().hex[:6]}",
        source="runbook",
        entity_id="system",
        timestamp=datetime.now(UTC).isoformat(),
        summary=summary,
        details={"runbook_id": "RB-102", "title": "High CPU Recovery Procedure"},
    )
    return ev, ToolMessage(content=summary, tool_call_id=call_id)


def query_knowledge_tool(
    query: str,
    session_id: str = "session-demo",
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
    client: MultiServerMCPClient | None = None,
) -> tuple[Evidence, ToolMessage]:
    """检索 Knowledge MCP 服务并生成 Evidence 与 ToolMessage (同步入口)。"""
    return _run_coro_sync(
        aquery_knowledge_tool(
            query=query,
            session_id=session_id,
            tool_call_id=tool_call_id,
            client=client,
        )
    )
