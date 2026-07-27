from evaluator.efficiency import EfficiencyEvaluator
from evaluator.schema import GroundTruth
from runtime.schema import BlackboardState


def test_efficiency_evaluation_round_one():
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
    assert score.raw_score == 1.0
    assert score.weighted_score == 10.0


def test_efficiency_evaluation_max_rounds():
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
        "current_round": 5,
        "max_rounds": 5,
        "next_steps": [],
        "diagnosis_report": None,
        "status": "COMPLETED",
    }
    evaluator = EfficiencyEvaluator()
    score = evaluator.evaluate(state, gt)
    assert abs(score.raw_score - 0.2) < 1e-4
    assert abs(score.weighted_score - 2.0) < 1e-4
