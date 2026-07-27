from typing import Any, Literal

from pydantic import BaseModel, Field

from simulator.scenario import Scenario


class TimelineEvent(BaseModel):
    tick: int
    entity_id: str
    metric_name: str | None = None
    expected_value: float | None = None
    expected_timestamp: str | None = None
    log_keyword: str | None = None
    description: str = ""


class GroundTruth(BaseModel):
    scenario_name: str
    root_cause_service: str
    root_cause_entity: str
    failure_type: str
    expected_tools: list[str] = Field(default_factory=list)
    expected_services: list[str] = Field(default_factory=list)
    expected_metrics: list[str] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)

    @classmethod
    def from_scenario(cls, scenario: Scenario) -> "GroundTruth":
        gt_data = getattr(scenario, "ground_truth_data", {}) or {}
        return cls(
            scenario_name=scenario.name,
            root_cause_service=gt_data.get("root_cause_service", ""),
            root_cause_entity=gt_data.get("root_cause_entity", ""),
            failure_type=gt_data.get("failure_type", ""),
            expected_tools=gt_data.get("expected_tools", []),
            expected_services=gt_data.get("expected_services", []),
            expected_metrics=gt_data.get("expected_metrics", []),
            timeline=[TimelineEvent(**t) for t in gt_data.get("timeline", [])],
        )


class DimensionScore(BaseModel):
    dimension: Literal["root_cause", "path_recall", "anti_hallucination", "efficiency"]
    raw_score: float
    weight: float
    weighted_score: float
    details: dict[str, Any] = Field(default_factory=dict)


class EvaluationScorecard(BaseModel):
    scenario_name: str
    root_cause_score: DimensionScore
    path_recall_score: DimensionScore
    anti_hallucination_score: DimensionScore
    efficiency_score: DimensionScore
    total_score: float
    pass_threshold: float = 60.0
    status: Literal["PASSED", "FAILED"]
    summary: str
