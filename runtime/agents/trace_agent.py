"""分布式调用链检索节点。

当前为轻量工具执行节点：根据 suspect_entities 和 incident_alert 中的 trace_id
调用 query_trace_tool 查询调用链详情，将结果写入 evidences。不含 LLM 推理。

后续如需深度链路分析（如自动定位慢 Span、根因 Span 推理），
可在此模块中引入 LLM 调用，升级为完整 Agent。"""

from typing import Any

from runtime.agents.utils import get_target_entities
from runtime.schema import BlackboardState
from runtime.tools.mcp_tools import query_trace_tool


def trace_node(state: BlackboardState) -> dict[str, Any]:
    entities = get_target_entities(state)
    alert = state.get("incident_alert", {})
    trace_id = alert.get("trace_id", "tr-88902")
    session_id = alert.get("session_id", "demo_session")
    evidences = []
    messages = []
    for target in entities:
        ev, msg = query_trace_tool(
            entity_id=target,
            trace_id=trace_id,
            session_id=session_id,
        )
        evidences.append(ev)
        messages.append(msg)
    return {"evidences": evidences, "messages": messages}
