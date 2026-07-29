"""评估器数据结构与 Schema 定义模块。

包含评测 GroundTruth、时间线事件 TimelineEvent、维度得分 DimensionScore 以及综合评估成绩单 EvaluationScorecard 的 Pydantic 模型。
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

from simulator.scenario import Scenario


class TimelineEvent(BaseModel):
    """故障演进时间线上的期望事件。

    Attributes:
        tick: 事件发生的仿真 Tick 步数。
        entity_id: 关联的实体/资源 ID (如服务名或容器名)。
        metric_name: 预期异常指标名称 (可选)。
        expected_value: 预期指标数值 (可选)。
        expected_timestamp: 预期事件 ISO 时间戳 (可选)。
        log_keyword: 预期日志中的关键匹配词 (可选)。
        description: 事件描述。
    """

    tick: int
    entity_id: str
    metric_name: str | None = None
    expected_value: float | None = None
    expected_timestamp: str | None = None
    log_keyword: str | None = None
    description: str = ""


class GroundTruth(BaseModel):
    """场景评估的标准基准真值 (Ground Truth)。

    定义场景中的实际根因服务、故障实体、故障类型、期望调用的工具/服务列表及时间线事件。
    """

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
        """从 Scenario 物理场景配置中提取并构建 GroundTruth 实例。"""
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
    """评估引擎单维度得分结构。

    Attributes:
        dimension: 评估维度标识 ("root_cause", "path_recall", "anti_hallucination", "efficiency")。
        raw_score: 原始得分百分比 (0.0 ~ 1.0)。
        weight: 维度权重。
        weighted_score: 加权后的综合分值 (0.0 ~ weight * 100.0)。
        details: 得分计算过程细节与调试信息。
    """

    dimension: Literal["root_cause", "path_recall", "anti_hallucination", "efficiency"]
    raw_score: float
    weight: float
    weighted_score: float
    details: dict[str, Any] = Field(default_factory=dict)


class EvaluationScorecard(BaseModel):
    """综合评测成绩单 (Scorecard)。

    汇总各评估维度的得分、总分、是否通过基线阈值以及文本摘要。
    """

    scenario_name: str
    root_cause_score: DimensionScore
    path_recall_score: DimensionScore
    anti_hallucination_score: DimensionScore
    efficiency_score: DimensionScore
    total_score: float
    pass_threshold: float = 60.0
    status: Literal["PASSED", "FAILED"]
    summary: str
