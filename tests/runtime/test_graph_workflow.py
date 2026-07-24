from runtime.graph import build_diagnosis_graph, run_diagnosis_workflow


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


def test_graph_structure_compilation():
    graph = build_diagnosis_graph()
    assert graph is not None
