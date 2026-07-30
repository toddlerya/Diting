"""Prometheus 指标检索节点。

当前为轻量工具执行节点：根据 suspect_entities 调用 query_metrics_tool 查询 CPU 等指标，
将结果写入 evidences。不含 LLM 推理，由 Supervisor 决定何时以及针对哪些实体调用。

后续如需深度指标分析（如自动识别异常模式、时序趋势推理），
可在此模块中引入 LLM 调用，升级为完整 Agent。"""

from typing import Any

from runtime.agents.utils import get_target_entities
from runtime.schema import BlackboardState
from runtime.tools.mcp_tools import query_metrics_tool


def metrics_node(state: BlackboardState) -> dict[str, Any]:
    entities = get_target_entities(state)
    session_id = state.get("incident_alert", {}).get("session_id", "demo_session")
    evidences = []
    messages = []
    for target in entities:
        prefix = target.lower().replace("service", "").replace("-", "_")
        # 尝试查询实体专属 CPU/延迟指标以及全局共享利用率指标
        query_candidates = [f"{prefix}_cpu_usage", f"{prefix}_latency", "redis_utilization"]
        for q in query_candidates:
            ev, msg = query_metrics_tool(
                entity_id=target,
                query=q,
                session_id=session_id,
            )
            # 若查到有效非空数值或为专属指标，保存为证据
            if (
                ev.details.get("metric_val")
                and isinstance(ev.details["metric_val"], dict)
                and ev.details["metric_val"].get("value") is not None
            ):
                evidences.append(ev)
                messages.append(msg)
                break
        else:
            # 兜底生成首个候选指标证据
            ev, msg = query_metrics_tool(
                entity_id=target,
                query=query_candidates[0],
                session_id=session_id,
            )
            evidences.append(ev)
            messages.append(msg)
    return {"evidences": evidences, "messages": messages}
