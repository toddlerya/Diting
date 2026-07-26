"""Loki 日志检索节点。

当前为轻量工具执行节点：根据 suspect_entities 调用 query_logs_tool 查询异常日志，
将结果写入 evidences。不含 LLM 推理，由 Supervisor 决定何时以及针对哪些实体调用。

后续如需深度日志分析（如自动提取异常模式、跨实体日志关联），
可在此模块中引入 LLM 调用，升级为完整 Agent。"""

from typing import Any

from runtime.agents.utils import get_target_entities
from runtime.schema import BlackboardState
from runtime.tools.mcp_tools import query_logs_tool


def logs_node(state: BlackboardState) -> dict[str, Any]:
    entities = get_target_entities(state)
    session_id = state.get("incident_alert", {}).get("session_id", "demo_session")
    evidences = []
    messages = []
    for target in entities:
        ev, msg = query_logs_tool(
            entity_id=target,
            query="Exception",
            session_id=session_id,
        )
        evidences.append(ev)
        messages.append(msg)
    return {"evidences": evidences, "messages": messages}
