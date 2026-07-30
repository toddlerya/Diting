from runtime.graph import build_diagnosis_graph, route_supervisor, run_diagnosis_workflow


def test_full_diagnosis_workflow():
    alert = {
        "alert_name": "HighCpuUsage",
        "service": "order-service",
        "timestamp": "2026-07-24T00:00:00+00:00",
    }
    result = run_diagnosis_workflow(alert_dict=alert, thread_id="incident-test-001")
    assert result["status"] == "COMPLETED"
    assert result["diagnosis_report"] is not None
    assert result["diagnosis_report"].root_cause_entity == "order-service"
    assert len(result["evidences"]) >= 3
    assert len(result["matched_runbooks"]) >= 1
    assert result["matched_runbooks"][0]["runbook_id"] in {"RB-102", "service_oom.md"}


def test_graph_structure_compilation():
    graph = build_diagnosis_graph()
    assert graph is not None


def test_memory_saver_checkpoint_state_inspection():
    alert = {
        "alert_name": "HighMemoryUsage",
        "service": "payment-service",
        "timestamp": "2026-07-24T00:00:00+00:00",
    }
    graph = build_diagnosis_graph()
    config = {"configurable": {"thread_id": "checkpoint-thread-002"}}
    initial_state = {
        "messages": [],
        "incident_alert": alert,
        "suspect_entities": ["payment-service"],
        "evidences": [],
        "matched_runbooks": [],
        "current_round": 1,
        "max_rounds": 5,
        "next_steps": [],
        "diagnosis_report": None,
        "status": "RUNNING",
    }
    graph.invoke(initial_state, config=config)
    snapshot = graph.get_state(config)
    assert snapshot.values["status"] == "COMPLETED"
    assert snapshot.values["diagnosis_report"].root_cause_entity == "payment-service"


def test_route_supervisor_invalid_node_filtering():
    state = {
        "messages": [],
        "incident_alert": {},
        "suspect_entities": ["order-service"],
        "evidences": [],
        "matched_runbooks": [],
        "current_round": 1,
        "max_rounds": 5,
        "next_steps": ["InvalidNode", "MetricsNode", "UnknownAgent"],
        "diagnosis_report": None,
        "status": "RUNNING",
    }
    routes = route_supervisor(state)
    assert routes == ["MetricsNode"]


def test_route_supervisor_max_rounds_forces_synthesizer():
    # current_round 在 Supervisor 入口已 +1，rounds_consumed = current_round - 1。
    # max_rounds=2 时，第 3 轮（current_round=3, rounds_consumed=2）应强制进入 Synthesizer，
    # 即使 Supervisor 仍想继续派发 MetricsNode。
    state = {
        "messages": [],
        "incident_alert": {},
        "suspect_entities": ["order-service"],
        "evidences": [],
        "matched_runbooks": [],
        "current_round": 3,
        "max_rounds": 2,
        "next_steps": ["MetricsNode"],
        "diagnosis_report": None,
        "status": "RUNNING",
    }
    assert route_supervisor(state) == ["Synthesizer"]


def test_route_supervisor_empty_steps_defaults_to_synthesizer():
    state = {
        "messages": [],
        "incident_alert": {},
        "suspect_entities": ["order-service"],
        "evidences": [],
        "matched_runbooks": [],
        "current_round": 1,
        "max_rounds": 5,
        "next_steps": [],
        "diagnosis_report": None,
        "status": "RUNNING",
    }
    assert route_supervisor(state) == ["Synthesizer"]


def test_workflow_respects_max_rounds():
    # max_rounds=1 时，第 1 轮 Supervisor 使 current_round=2（rounds_consumed=1），
    # route 应返回 Synthesizer，工作流不得无限循环。
    alert = {
        "alert_name": "HighCpuUsage",
        "service": "order-service",
        "timestamp": "2026-07-24T00:00:00+00:00",
    }
    result = run_diagnosis_workflow(
        alert_dict=alert, thread_id="incident-maxrounds-001", max_rounds=1
    )
    assert result["status"] == "COMPLETED"
    assert result["current_round"] - 1 <= 1


def test_fallback_evidence_lowers_synthesizer_confidence():
    from runtime.agents.synthesizer import synthesizer_node
    from runtime.schema import Evidence

    state = {
        "messages": [],
        "incident_alert": {"service": "order-service"},
        "suspect_entities": ["order-service"],
        "evidences": [
            Evidence(
                id="ev-fb-1",
                source="metric",
                entity_id="order-service",
                timestamp="2026-07-24T00:00:00+00:00",
                summary="fallback",
                relevance_score=0.0,
                details={"is_fallback": True},
            )
        ],
        "matched_runbooks": [],
        "current_round": 2,
        "max_rounds": 5,
        "next_steps": ["Synthesizer"],
        "diagnosis_report": None,
        "status": "RUNNING",
    }
    update = synthesizer_node(state)
    report = update["diagnosis_report"]
    assert report.confidence <= 0.5
    assert "fallback" in report.summary.lower()
