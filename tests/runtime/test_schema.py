from runtime.schema import BlackboardState, DiagnosisReport, Evidence


def test_evidence_creation():
    ev = Evidence(
        id="ev-1",
        source="metric",
        entity_id="order-service",
        timestamp="2026-07-24T00:00:00+00:00",
        summary="High CPU usage 95%",
        details={"cpu_util": 0.95},
    )
    assert ev.source == "metric"
    assert ev.timestamp.endswith("+00:00")


def test_diagnosis_report_creation():
    report = DiagnosisReport(
        root_cause_entity="order-service",
        failure_type="CPU_BURST",
        confidence=0.95,
        evidence_ids=["ev-1"],
        summary="Order service CPU spike caused crash",
        recommended_actions=["Scale up pod"],
    )
    assert report.confidence == 0.95


def test_blackboard_state_initialization():
    state: BlackboardState = {
        "messages": [],
        "incident_alert": {"alert_name": "HighLatency"},
        "suspect_entities": ["order-service"],
        "evidences": [],
        "matched_runbooks": [],
        "current_round": 1,
        "max_rounds": 5,
        "next_steps": ["MetricsNode"],
        "diagnosis_report": None,
        "status": "RUNNING",
    }
    assert state["status"] == "RUNNING"
    assert state["next_steps"] == ["MetricsNode"]
