"""编排器 / Supervisor Agent 节点。

完整 LLM Agent：使用 SUPERVISOR_PROMPT + with_structured_output(SupervisorDecision)
决定下一轮派发哪些 Specialist 节点以及更新 suspect_entities。

当前功能：多轮并行派发逻辑。后续可扩展为更复杂的编排策略
（如基于置信度的动态终止、优先级队列、人机协同审批）。"""

import json
from typing import Any

from loguru import logger

from runtime.agents.utils import format_evidences_for_prompt
from runtime.llm import get_llm
from runtime.mock_llm import MockLLMClient
from runtime.prompts import SUPERVISOR_PROMPT
from runtime.schema import BlackboardState, SupervisorDecision

NODE_NAME_MAP = {
    "metricsnode": "MetricsNode",
    "dispatch_metrics_node": "MetricsNode",
    "metrics_node": "MetricsNode",
    "logsnode": "LogsNode",
    "dispatch_logs_node": "LogsNode",
    "logs_node": "LogsNode",
    "tracenode": "TraceNode",
    "dispatch_trace_node": "TraceNode",
    "trace_node": "TraceNode",
    "knowledgenode": "KnowledgeNode",
    "dispatch_knowledge_node": "KnowledgeNode",
    "knowledge_node": "KnowledgeNode",
    "synthesizer": "Synthesizer",
}


def _invoke_supervisor_llm(state: BlackboardState) -> dict[str, Any] | None:
    llm = get_llm()
    if not llm:
        return None

    try:
        curr_round = state.get("current_round", 1)
        max_rounds = state.get("max_rounds", 5)
        evidences = format_evidences_for_prompt(state.get("evidences", []))
        suspects = state.get("suspect_entities", [])
        alert = state.get("incident_alert", {})

        user_content = json.dumps(
            {
                "current_round": curr_round,
                "incident_alert": alert,
                "suspect_entities": suspects,
                "evidences_collected": evidences,
                "matched_runbooks": state.get("matched_runbooks", []),
            },
            ensure_ascii=False,
            default=str,
        )

        logger.info(
            f"🚀 [LLM Request] Agent=Supervisor | Round={curr_round}/{max_rounds} | Model={llm.model_name}"
        )
        logger.debug(f"📝 [LLM Request Prompt - Supervisor]\n{user_content}")

        chain = SUPERVISOR_PROMPT | llm.with_structured_output(SupervisorDecision)
        decision: SupervisorDecision = chain.invoke(
            {
                "current_round": curr_round,
                "max_rounds": max_rounds,
                "blackboard_state": user_content,
            }
        )

        normalized_steps = [NODE_NAME_MAP.get(s.lower(), s) for s in decision.next_steps]

        logger.info(
            f"✅ [LLM Parsed Response - Supervisor] Next Steps={normalized_steps} | Suspects={decision.suspect_entities} | Reasoning={decision.reasoning}"
        )

        res_dict = {
            "next_steps": normalized_steps,
        }
        if decision.suspect_entities:
            res_dict["suspect_entities"] = decision.suspect_entities
        return res_dict
    except Exception as e:
        logger.warning(
            f"⚠️ [LLM Failure] Supervisor LLM call failed ({e}), falling back to MockLLM."
        )
        return None


def supervisor_node(state: BlackboardState) -> dict[str, Any]:
    decision = _invoke_supervisor_llm(state)
    if not decision:
        client = MockLLMClient()
        decision = client.invoke(state)

    update: dict[str, Any] = {
        "next_steps": decision.get("next_steps", ["Synthesizer"]),
        "current_round": state.get("current_round", 1) + 1,
    }
    if "suspect_entities" in decision:
        update["suspect_entities"] = decision["suspect_entities"]
    return update
