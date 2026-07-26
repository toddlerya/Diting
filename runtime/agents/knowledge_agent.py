"""运维知识库 / Runbook 检索节点。

当前为轻量工具执行节点：调用 query_knowledge_tool 检索匹配的运维 Runbook，
将结果写入 matched_runbooks。不含 LLM 推理。

后续如需深度知识推理（如根据故障现象自动匹配多篇文档、推理修复步骤），
可在此模块中引入 LLM 调用，升级为完整 Agent。"""

from typing import Any

from runtime.schema import BlackboardState
from runtime.tools.mcp_tools import query_knowledge_tool


def knowledge_node(state: BlackboardState) -> dict[str, Any]:
    ev, msg = query_knowledge_tool(query="High CPU load troubleshooting")
    runbook_info = {
        "runbook_id": ev.details.get("runbook_id", "RB-102"),
        "title": ev.details.get("title", "High CPU Recovery Procedure"),
    }
    return {
        "evidences": [ev],
        "messages": [msg],
        "matched_runbooks": [runbook_info],
    }
