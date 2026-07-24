import uuid
from datetime import UTC, datetime
from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId

from runtime.schema import Evidence


def query_metrics_tool(
    entity_id: str,
    query: str,
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
) -> tuple[Evidence, ToolMessage]:
    """查询 Prometheus 指标并生成 Evidence 与 ToolMessage。"""
    call_id = tool_call_id or f"call_{uuid.uuid4().hex[:8]}"
    summary = f"Prometheus query '{query}' for {entity_id}: detected CPU/memory spike"
    ev = Evidence(
        id=f"ev-metric-{uuid.uuid4().hex[:6]}",
        source="metric",
        entity_id=entity_id,
        timestamp=datetime.now(UTC).isoformat(),
        summary=summary,
        details={"query": query, "metric_val": 92.5},
    )
    msg = ToolMessage(content=summary, tool_call_id=call_id)
    return ev, msg


def query_logs_tool(
    entity_id: str,
    query: str,
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
) -> tuple[Evidence, ToolMessage]:
    """查询 Loki 日志并生成 Evidence 与 ToolMessage。"""
    call_id = tool_call_id or f"call_{uuid.uuid4().hex[:8]}"
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
    msg = ToolMessage(content=summary, tool_call_id=call_id)
    return ev, msg


def query_trace_tool(
    entity_id: str,
    trace_id: str,
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
) -> tuple[Evidence, ToolMessage]:
    """查询 Trace 调用链并生成 Evidence 与 ToolMessage。"""
    call_id = tool_call_id or f"call_{uuid.uuid4().hex[:8]}"
    summary = f"Trace query '{trace_id}' for {entity_id}: span latency exceeded 2500ms"
    ev = Evidence(
        id=f"ev-trace-{uuid.uuid4().hex[:6]}",
        source="trace",
        entity_id=entity_id,
        timestamp=datetime.now(UTC).isoformat(),
        summary=summary,
        details={"trace_id": trace_id, "duration_ms": 2540.0},
    )
    msg = ToolMessage(content=summary, tool_call_id=call_id)
    return ev, msg


def query_knowledge_tool(
    query: str,
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
) -> tuple[Evidence, ToolMessage]:
    """检索 Knowledge 运维 Wiki 并生成 Evidence 与 ToolMessage。"""
    call_id = tool_call_id or f"call_{uuid.uuid4().hex[:8]}"
    summary = f"Knowledge base runbook search '{query}': Matched High CPU Runbook RB-102"
    ev = Evidence(
        id=f"ev-kb-{uuid.uuid4().hex[:6]}",
        source="runbook",
        entity_id="system",
        timestamp=datetime.now(UTC).isoformat(),
        summary=summary,
        details={"runbook_id": "RB-102", "title": "High CPU Recovery Procedure"},
    )
    msg = ToolMessage(content=summary, tool_call_id=call_id)
    return ev, msg
