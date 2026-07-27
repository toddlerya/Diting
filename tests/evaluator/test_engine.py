from langchain_core.messages import AIMessage

from evaluator.engine import EvaluatorEngine
from evaluator.schema import EvaluationScorecard
from runtime.schema import BlackboardState, DiagnosisReport, Evidence
from simulator.scenario import Scenario


def test_evaluator_engine_full_flow():
    sc_data = {
        "name": "redis_leak_scenario",
        "description": "Redis leak test",
        "ground_truth": {
            "root_cause_service": "PaymentService",
            "root_cause_entity": "PaymentService-RedisPool",
            "failure_type": "REDIS_POOL_LEAK",
            "expected_tools": ["query_metrics"],
            "expected_services": ["PaymentService"],
            "timeline": [
                {
                    "tick": 10,
                    "entity_id": "PaymentService",
                    "log_keyword": "Timeout waiting for connection",
                }
            ],
        },
        "steps": [],
    }
    sc = Scenario(
        "redis_leak_scenario",
        "Redis leak test",
        [],
        seed=42,
        ground_truth_data=sc_data["ground_truth"],
    )
    report = DiagnosisReport(
        root_cause_entity="PaymentService-RedisPool",
        failure_type="REDIS_POOL_LEAK",
        confidence=1.0,
        evidence_ids=["ev-1"],
        summary="Redis pool leaked",
    )
    ev = Evidence(
        id="ev-1",
        source="log",
        entity_id="PaymentService",
        timestamp="2026-07-27T00:00:10+00:00",
        summary="Timeout waiting for connection",
    )
    msg = AIMessage(
        content="",
        tool_calls=[
            {"name": "query_metrics", "args": {"entity_id": "PaymentService"}, "id": "call_1"}
        ],
    )
    state: BlackboardState = {
        "messages": [msg],
        "incident_alert": {},
        "suspect_entities": ["PaymentService"],
        "evidences": [ev],
        "matched_runbooks": [],
        "current_round": 1,
        "max_rounds": 5,
        "next_steps": [],
        "diagnosis_report": report,
        "status": "COMPLETED",
    }
    engine = EvaluatorEngine(pass_threshold=60.0)
    scorecard = engine.evaluate(state, sc)

    assert isinstance(scorecard, EvaluationScorecard)
    assert scorecard.root_cause_score.raw_score == 1.0
    assert scorecard.total_score == 100.0
    assert scorecard.status == "PASSED"
