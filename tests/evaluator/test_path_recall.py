import pytest
from langchain_core.messages import AIMessage

from evaluator.path_recall import PathRecallEvaluator
from evaluator.schema import GroundTruth
from runtime.schema import BlackboardState


def test_path_recall_full_match():
    gt = GroundTruth(
        scenario_name="redis_leak",
        root_cause_service="PaymentService",
        root_cause_entity="PaymentService-RedisPool",
        failure_type="REDIS_POOL_LEAK",
        expected_tools=["query_metrics", "query_logs"],
        expected_services=["Gateway", "PaymentService"],
    )
    msg = AIMessage(
        content="",
        tool_calls=[
            {"name": "query_metrics", "args": {"entity_id": "Gateway"}, "id": "tc1"},
            {"name": "query_logs", "args": {"service": "PaymentService"}, "id": "tc2"},
        ],
    )
    state: BlackboardState = {
        "messages": [msg],
        "incident_alert": {},
        "suspect_entities": ["Gateway", "PaymentService"],
        "evidences": [],
        "matched_runbooks": [],
        "current_round": 1,
        "max_rounds": 5,
        "next_steps": [],
        "diagnosis_report": None,
        "status": "COMPLETED",
    }
    evaluator = PathRecallEvaluator()
    score = evaluator.evaluate(state, gt)
    assert score.raw_score == 1.0
    assert score.weighted_score == 25.0
    assert score.dimension == "path_recall"


def test_path_recall_partial_match():
    gt = GroundTruth(
        scenario_name="partial_match_scenario",
        root_cause_service="PaymentService",
        root_cause_entity="PaymentService-DB",
        failure_type="DB_LATENCY",
        expected_tools=["query_metrics", "query_logs", "query_traces"],
        expected_services=["Gateway", "PaymentService", "OrderService"],
    )
    msg = AIMessage(
        content="",
        tool_calls=[
            {"name": "query_metrics", "args": {"entity_id": "Gateway"}, "id": "tc1"},
            {"name": "query_logs", "args": {"service": "PaymentService"}, "id": "tc2"},
        ],
    )
    state: BlackboardState = {
        "messages": [msg],
        "incident_alert": {},
        "suspect_entities": ["Gateway", "PaymentService"],
        "evidences": [],
        "matched_runbooks": [],
        "current_round": 1,
        "max_rounds": 5,
        "next_steps": [],
        "diagnosis_report": None,
        "status": "COMPLETED",
    }
    evaluator = PathRecallEvaluator()
    score = evaluator.evaluate(state, gt)
    assert pytest.approx(score.raw_score, 1e-4) == 0.8
    assert pytest.approx(score.weighted_score, 1e-4) == 20.0


def test_path_recall_empty_expected_tools():
    gt = GroundTruth(
        scenario_name="test",
        root_cause_service="S1",
        root_cause_entity="E1",
        failure_type="F1",
        expected_tools=[],
        expected_services=[],
    )
    state: BlackboardState = {
        "messages": [],
        "incident_alert": {},
        "suspect_entities": [],
        "evidences": [],
        "matched_runbooks": [],
        "current_round": 1,
        "max_rounds": 5,
        "next_steps": [],
        "diagnosis_report": None,
        "status": "COMPLETED",
    }
    evaluator = PathRecallEvaluator()
    score = evaluator.evaluate(state, gt)
    assert score.raw_score == 1.0
    assert score.weighted_score == 25.0


def test_path_recall_empty_expected_with_actual_calls():
    gt = GroundTruth(
        scenario_name="test",
        root_cause_service="S1",
        root_cause_entity="E1",
        failure_type="F1",
        expected_tools=[],
        expected_services=[],
    )
    msg = AIMessage(
        content="",
        tool_calls=[
            {"name": "query_metrics", "args": {"entity_id": "Gateway"}, "id": "tc1"},
        ],
    )
    state: BlackboardState = {
        "messages": [msg],
        "incident_alert": {},
        "suspect_entities": [],
        "evidences": [],
        "matched_runbooks": [],
        "current_round": 1,
        "max_rounds": 5,
        "next_steps": [],
        "diagnosis_report": None,
        "status": "COMPLETED",
    }
    evaluator = PathRecallEvaluator()
    score = evaluator.evaluate(state, gt)
    assert score.raw_score == 0.5
    assert score.weighted_score == 12.5
