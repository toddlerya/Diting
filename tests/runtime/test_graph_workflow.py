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
    assert len(result["evidences"]) >= 4
    assert len(result["matched_runbooks"]) >= 1


def test_graph_structure_compilation():
    graph = build_diagnosis_graph()
    assert graph is not None


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
