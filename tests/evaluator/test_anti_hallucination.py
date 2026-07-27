from evaluator.anti_hallucination import AntiHallucinationEvaluator
from evaluator.schema import GroundTruth, TimelineEvent
from runtime.schema import BlackboardState, Evidence


def test_anti_hallucination_valid_metric_and_log():
    gt = GroundTruth(
        scenario_name="redis_leak",
        root_cause_service="PaymentService",
        root_cause_entity="PaymentService-RedisPool",
        failure_type="REDIS_POOL_LEAK",
        timeline=[
            TimelineEvent(
                tick=10,
                entity_id="PaymentService",
                metric_name="active_connections",
                expected_value=50.0,
                expected_timestamp="2026-07-27T00:00:10+00:00",
                log_keyword="Timeout waiting for connection",
            )
        ],
    )
    ev_log = Evidence(
        id="ev-1",
        source="log",
        entity_id="PaymentService",
        timestamp="2026-07-27T00:00:12+00:00",  # 2 seconds delta (within +-5s)
        summary="Timeout waiting for connection after 500ms",
    )
    ev_metric = Evidence(
        id="ev-2",
        source="metric",
        entity_id="PaymentService",
        timestamp="2026-07-27T00:00:10+00:00",
        summary="High active connections",
        details={"value": 52.0},  # (52-50)/50 = 4% relative error (within <=10%)
    )
    state: BlackboardState = {
        "messages": [],
        "incident_alert": {},
        "suspect_entities": [],
        "evidences": [ev_log, ev_metric],
        "matched_runbooks": [],
        "current_round": 1,
        "max_rounds": 5,
        "next_steps": [],
        "diagnosis_report": None,
        "status": "COMPLETED",
    }
    evaluator = AntiHallucinationEvaluator()
    score = evaluator.evaluate(state, gt)
    assert score.raw_score == 1.0
    assert score.weighted_score == 25.0


def test_anti_hallucination_numerical_error_exceeded():
    gt = GroundTruth(
        scenario_name="redis_leak",
        root_cause_service="PaymentService",
        root_cause_entity="PaymentService-RedisPool",
        failure_type="REDIS_POOL_LEAK",
        timeline=[
            TimelineEvent(
                tick=10,
                entity_id="PaymentService",
                metric_name="active_connections",
                expected_value=50.0,
            )
        ],
    )
    ev_fake = Evidence(
        id="ev-fake",
        source="metric",
        entity_id="PaymentService",
        timestamp="2026-07-27T00:00:10+00:00",
        summary="Hallucinated connection metric",
        details={"value": 90.0},  # (90-50)/50 = 80% error (>10%)
        relevance_score=0.0,  # Ensure heuristic low score won't trigger
    )
    state: BlackboardState = {
        "messages": [],
        "incident_alert": {},
        "suspect_entities": [],
        "evidences": [ev_fake],
        "matched_runbooks": [],
        "current_round": 1,
        "max_rounds": 5,
        "next_steps": [],
        "diagnosis_report": None,
        "status": "COMPLETED",
    }
    evaluator = AntiHallucinationEvaluator()
    score = evaluator.evaluate(state, gt)
    assert score.raw_score == 0.0
    assert score.weighted_score == 0.0


def test_anti_hallucination_empty_evidence():
    gt = GroundTruth(
        scenario_name="redis_leak",
        root_cause_service="PaymentService",
        root_cause_entity="PaymentService-RedisPool",
        failure_type="REDIS_POOL_LEAK",
        timeline=[],
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
    evaluator = AntiHallucinationEvaluator()
    score = evaluator.evaluate(state, gt)
    assert score.raw_score == 0.0
    assert score.weighted_score == 0.0
    assert "No evidence provided" in score.details.get("reason", "")


def test_anti_hallucination_timestamp_delta_exceeded():
    gt = GroundTruth(
        scenario_name="redis_leak",
        root_cause_service="PaymentService",
        root_cause_entity="PaymentService-RedisPool",
        failure_type="REDIS_POOL_LEAK",
        timeline=[
            TimelineEvent(
                tick=10,
                entity_id="PaymentService",
                metric_name="active_connections",
                expected_value=50.0,
                expected_timestamp="2026-07-27T00:00:10+00:00",
            )
        ],
    )
    ev_late = Evidence(
        id="ev-late",
        source="metric",
        entity_id="PaymentService",
        timestamp="2026-07-27T00:00:20+00:00",  # 10s delta (> 5.0s)
        summary="Late metric connection check",
        details={"value": 50.0},
        relevance_score=0.0,
    )
    state: BlackboardState = {
        "messages": [],
        "incident_alert": {},
        "suspect_entities": [],
        "evidences": [ev_late],
        "matched_runbooks": [],
        "current_round": 1,
        "max_rounds": 5,
        "next_steps": [],
        "diagnosis_report": None,
        "status": "COMPLETED",
    }
    evaluator = AntiHallucinationEvaluator()
    score = evaluator.evaluate(state, gt)
    assert score.raw_score == 0.0
    assert score.weighted_score == 0.0
