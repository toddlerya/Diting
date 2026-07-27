from evaluator.schema import (
    DimensionScore,
    EvaluationScorecard,
    GroundTruth,
    TimelineEvent,
)
from simulator.scenario import Scenario


def test_timeline_event_creation():
    event = TimelineEvent(
        tick=15,
        entity_id="Node-1",
        metric_name="disk_util",
        expected_value=0.96,
        expected_timestamp="2026-07-27T00:00:15+00:00",
        log_keyword="Disk utility threshold exceeded",
    )
    assert event.tick == 15
    assert event.expected_value == 0.96
    assert event.expected_timestamp.endswith("+00:00")


def test_ground_truth_from_scenario():
    data = {
        "name": "test_scenario",
        "description": "test description",
        "ground_truth": {
            "root_cause_service": "PaymentService",
            "root_cause_entity": "PaymentService-RedisPool",
            "failure_type": "REDIS_POOL_LEAK",
            "expected_tools": ["query_metrics", "query_logs"],
            "expected_services": ["Gateway", "PaymentService"],
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
    sc = Scenario("test_scenario", "desc", [], seed=42, ground_truth_data=data["ground_truth"])
    gt = GroundTruth.from_scenario(sc)
    assert gt.root_cause_service == "PaymentService"
    assert gt.failure_type == "REDIS_POOL_LEAK"
    assert len(gt.timeline) == 1
    assert gt.timeline[0].log_keyword == "Timeout waiting for connection"


def test_evaluation_scorecard_status():
    dim_rc = DimensionScore(dimension="root_cause", raw_score=1.0, weight=0.4, weighted_score=40.0)
    dim_pr = DimensionScore(
        dimension="path_recall", raw_score=1.0, weight=0.25, weighted_score=25.0
    )
    dim_ah = DimensionScore(
        dimension="anti_hallucination", raw_score=1.0, weight=0.25, weighted_score=25.0
    )
    dim_eff = DimensionScore(dimension="efficiency", raw_score=1.0, weight=0.1, weighted_score=10.0)

    card = EvaluationScorecard(
        scenario_name="test_scenario",
        root_cause_score=dim_rc,
        path_recall_score=dim_pr,
        anti_hallucination_score=dim_ah,
        efficiency_score=dim_eff,
        total_score=100.0,
        pass_threshold=60.0,
        status="PASSED",
        summary="Perfect score",
    )
    assert card.status == "PASSED"
