from evaluator.root_cause import RootCauseEvaluator
from evaluator.schema import GroundTruth
from runtime.schema import DiagnosisReport


def test_root_cause_exact_match():
    gt = GroundTruth(
        scenario_name="redis_leak",
        root_cause_service="PaymentService",
        root_cause_entity="PaymentService-RedisPool",
        failure_type="REDIS_POOL_LEAK",
    )
    report = DiagnosisReport(
        root_cause_entity="PaymentService-RedisPool",
        failure_type="REDIS_POOL_LEAK",
        confidence=1.0,
        evidence_ids=["ev-1"],
        summary="Redis pool leak in PaymentService",
    )
    evaluator = RootCauseEvaluator()
    score = evaluator.evaluate(report, gt)
    assert score.raw_score == 1.0
    assert score.weighted_score == 40.0


def test_root_cause_service_match():
    gt = GroundTruth(
        scenario_name="redis_leak",
        root_cause_service="PaymentService",
        root_cause_entity="PaymentService-RedisPool",
        failure_type="REDIS_POOL_LEAK",
    )
    report = DiagnosisReport(
        root_cause_entity="PaymentService",
        failure_type="REDIS_LEAK",
        confidence=0.8,
        evidence_ids=["ev-1"],
        summary="PaymentService issue",
    )
    evaluator = RootCauseEvaluator()
    score = evaluator.evaluate(report, gt)
    assert abs(score.raw_score - 0.608) < 1e-4


def test_root_cause_no_match():
    gt = GroundTruth(
        scenario_name="redis_leak",
        root_cause_service="PaymentService",
        root_cause_entity="PaymentService-RedisPool",
        failure_type="REDIS_POOL_LEAK",
    )
    report = DiagnosisReport(
        root_cause_entity="UserService",
        failure_type="CPU_BURST",
        confidence=0.9,
        evidence_ids=["ev-1"],
        summary="Wrong entity and failure type",
    )
    evaluator = RootCauseEvaluator()
    score = evaluator.evaluate(report, gt)
    assert score.raw_score == 0.0
    assert score.weighted_score == 0.0


def test_root_cause_none_report():
    gt = GroundTruth(
        scenario_name="redis_leak",
        root_cause_service="PaymentService",
        root_cause_entity="PaymentService-RedisPool",
        failure_type="REDIS_POOL_LEAK",
    )
    evaluator = RootCauseEvaluator()
    score = evaluator.evaluate(None, gt)
    assert score.raw_score == 0.0
    assert score.weighted_score == 0.0
    assert score.details["reason"] == "No diagnosis report provided"
