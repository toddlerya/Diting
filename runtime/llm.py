import json
import os
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from loguru import logger

from runtime.schema import BlackboardState, DiagnosisReport, SupervisorDecision

load_dotenv()


def get_llm(timeout: float = 60.0) -> ChatOpenAI | None:
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    base_url = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_API_BASE")
    model = os.getenv("LLM_MODEL", "Qwen/Qwen3.5-35B-A3B")
    return ChatOpenAI(
        api_key=api_key,
        base_url=base_url,
        model=model,
        temperature=0.1,
        request_timeout=timeout,
    )


def invoke_supervisor_llm(state: BlackboardState) -> dict[str, Any] | None:
    llm = get_llm()
    if not llm:
        return None

    try:
        curr_round = state.get("current_round", 1)
        max_rounds = state.get("max_rounds", 5)
        evidences = [e.model_dump() for e in state.get("evidences", [])]
        suspects = state.get("suspect_entities", [])
        alert = state.get("incident_alert", {})

        system_prompt = (
            "You are the Orchestrator/Supervisor for a distributed microservice root cause analysis platform (Diting).\n"
            f"Rule: Current round is {curr_round} of {max_rounds}. "
            "In round 1, dispatch relevant diagnostic nodes (e.g., MetricsNode, LogsNode, TraceNode, KnowledgeNode).\n"
            "If sufficient evidence is collected or max rounds reached or in round 2+, choose ['Synthesizer']."
        )

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

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Current Blackboard State:\n{user_content}"),
        ]

        logger.info(
            f"🚀 [LLM Request] Agent=Supervisor | Round={curr_round}/{max_rounds} | Model={llm.model_name}"
        )
        logger.debug(f"📝 [LLM Request Prompt - Supervisor]\n{user_content}")

        structured_llm = llm.with_structured_output(SupervisorDecision)
        decision: SupervisorDecision = structured_llm.invoke(messages)

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


def invoke_synthesizer_llm(state: BlackboardState) -> DiagnosisReport | None:
    llm = get_llm()
    if not llm:
        return None

    try:
        alert = state.get("incident_alert", {})
        evidences = [e.model_dump() for e in state.get("evidences", [])]
        runbooks = state.get("matched_runbooks", [])

        system_prompt = (
            "You are the Lead RCA Synthesizer for distributed microservices (Diting).\n"
            "Synthesize a formal root cause report based on the provided evidences and incident context."
        )

        user_content = json.dumps(
            {
                "incident_alert": alert,
                "suspect_entities": state.get("suspect_entities", []),
                "evidences": evidences,
                "matched_runbooks": runbooks,
            },
            ensure_ascii=False,
            default=str,
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Incident Evidences and Context:\n{user_content}"),
        ]

        logger.info(f"🚀 [LLM Request] Agent=Synthesizer | Model={llm.model_name}")
        logger.debug(f"📝 [LLM Request Prompt - Synthesizer]\n{user_content}")

        structured_llm = llm.with_structured_output(DiagnosisReport)
        report: DiagnosisReport = structured_llm.invoke(messages)

        logger.info(
            f"✅ [LLM Parsed Report - Synthesizer] RootCause={report.root_cause_entity} | Failure={report.failure_type} | Confidence={report.confidence}"
        )
        return report
    except Exception as e:
        logger.warning(
            f"⚠️ [LLM Failure] Synthesizer LLM call failed ({e}), falling back to mock report."
        )
        return None
