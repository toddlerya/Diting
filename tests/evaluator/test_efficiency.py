import pytest

from evaluator.efficiency import EfficiencyEvaluator
from evaluator.schema import GroundTruth
from runtime.schema import BlackboardState


def test_efficiency_evaluation_round_1():
    gt = GroundTruth(
        scenario_name="redis_leak",
        root_cause_service="PaymentService",
        root_cause_entity="PaymentService-RedisPool",
        failure_type="REDIS_POOL_LEAK",
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
    evaluator = EfficiencyEvaluator()
    score = evaluator.evaluate(state, gt)
    assert score.dimension == "efficiency"
    assert score.raw_score == 1.0
    assert score.weight == 0.10
    assert score.weighted_score == 10.0
    assert score.details["current_round"] == 1
    assert score.details["max_rounds"] == 5
    assert score.details["round_penalty"] == 0.0


def test_efficiency_evaluation_round_3():
    gt = GroundTruth(
        scenario_name="redis_leak",
        root_cause_service="PaymentService",
        root_cause_entity="PaymentService-RedisPool",
        failure_type="REDIS_POOL_LEAK",
    )
    state: BlackboardState = {
        "messages": [],
        "incident_alert": {},
        "suspect_entities": [],
        "evidences": [],
        "matched_runbooks": [],
        "current_round": 3,
        "max_rounds": 5,
        "next_steps": [],
        "diagnosis_report": None,
        "status": "COMPLETED",
    }
    evaluator = EfficiencyEvaluator()
    score = evaluator.evaluate(state, gt)
    assert score.raw_score == pytest.approx(0.6)
    assert score.weighted_score == pytest.approx(6.0)


def test_efficiency_evaluation_exceeds_max_rounds():
    gt = GroundTruth(
        scenario_name="redis_leak",
        root_cause_service="PaymentService",
        root_cause_entity="PaymentService-RedisPool",
        failure_type="REDIS_POOL_LEAK",
    )
    state: BlackboardState = {
        "messages": [],
        "incident_alert": {},
        "suspect_entities": [],
        "evidences": [],
        "matched_runbooks": [],
        "current_round": 10,
        "max_rounds": 5,
        "next_steps": [],
        "diagnosis_report": None,
        "status": "FAILED",
    }
    evaluator = EfficiencyEvaluator()
    score = evaluator.evaluate(state, gt)
    assert score.raw_score == 0.0
    assert score.weighted_score == 0.0


def test_efficiency_evaluation_defaults_and_edge_cases():
    gt = GroundTruth(
        scenario_name="test",
        root_cause_service="Svc",
        root_cause_entity="Ent",
        failure_type="FAIL",
    )
    # Empty blackboard state dictionary (using get with defaults)
    state: BlackboardState = {}
    evaluator = EfficiencyEvaluator()
    score = evaluator.evaluate(state, gt)
    assert score.details["current_round"] == 1
    assert score.details["max_rounds"] == 5
    assert score.raw_score == 1.0

    # Zero max_rounds safety check
    state_zero_rounds: BlackboardState = {"current_round": 1, "max_rounds": 0}
    score_zero = evaluator.evaluate(state_zero_rounds, gt)
    assert score_zero.details["max_rounds"] == 1
    assert score_zero.raw_score == 1.0
