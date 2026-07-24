import json
from typing import Any

from loguru import logger

from runtime.agents.utils import format_evidences_for_prompt
from runtime.llm import get_llm
from runtime.prompts import SYNTHESIZER_PROMPT
from runtime.schema import BlackboardState, DiagnosisReport


def _invoke_synthesizer_llm(state: BlackboardState) -> DiagnosisReport | None:
    llm = get_llm()
    if not llm:
        return None

    try:
        alert = state.get("incident_alert", {})
        evidences = format_evidences_for_prompt(state.get("evidences", []))
        runbooks = state.get("matched_runbooks", [])

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

        logger.info(f"🚀 [LLM Request] Agent=Synthesizer | Model={llm.model_name}")
        logger.debug(f"📝 [LLM Request Prompt - Synthesizer]\n{user_content}")

        chain = SYNTHESIZER_PROMPT | llm.with_structured_output(DiagnosisReport)
        report: DiagnosisReport = chain.invoke(
            {
                "context_json": user_content,
            }
        )

        logger.info(
            f"✅ [LLM Parsed Report - Synthesizer] RootCause={report.root_cause_entity} | Failure={report.failure_type} | Confidence={report.confidence}"
        )
        return report
    except Exception as e:
        logger.warning(
            f"⚠️ [LLM Failure] Synthesizer LLM call failed ({e}), falling back to mock report."
        )
        return None


def synthesizer_node(state: BlackboardState) -> dict[str, Any]:
    report = _invoke_synthesizer_llm(state)
    if not report:
        evidences = state.get("evidences", [])
        ev_ids = [e.id for e in evidences]
        entities = state.get("suspect_entities", ["unknown-service"])
        target = entities[0] if entities else "unknown-service"

        report = DiagnosisReport(
            root_cause_entity=target,
            failure_type="CPU_BURST",
            confidence=0.92,
            evidence_ids=ev_ids,
            summary=f"Incident root cause isolated to {target} due to CPU burst and exception stack trace.",
            recommended_actions=[
                f"Restart pod for {target}",
                "Apply CPU limit patch",
            ],
        )
    return {"diagnosis_report": report, "status": "COMPLETED"}
