from typing import Any

from runtime.schema import BlackboardState, DiagnosisReport


def synthesizer_node(state: BlackboardState) -> dict[str, Any]:
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
