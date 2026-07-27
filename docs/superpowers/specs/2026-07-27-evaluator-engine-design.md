# Diting (谛听) Evaluation Engine (Day 6 评估引擎) 详细设计说明书

## 1. 概述与目标

Evaluation Engine (评估引擎) 是 Diting (谛听) 平台的 Day 6 核心模块，用于针对给定故障剧本 (Scenario) 的 Ground Truth，对 Agent Runtime 输出的结构化诊断报告 (`DiagnosisReport`) 和排查过程轨迹 (`BlackboardState`) 进行自动化、多维度的 Benchmark 打分。

### 核心目标
1. **多维自动化打分**: 涵盖根因准确率 (Root Cause Accuracy 40%)、路径召回率 (Path Recall 25%)、抗幻觉真实度 (Anti-Hallucination 25%) 及资源效率 (Efficiency 10%)。
2. **确定性与打假逻辑**: 对 Agent 输出的 Pydantic `Evidence` 证据链进行物理事实反查与三阶过滤（时间窗口容差 $\pm 5\text{s}$、数值相对误差 $\le 10\%$、日志关键字匹配）。
3. **单源 Ground Truth**: 与 `Scenario` YAML 保持单一事实源，通过顶层 `ground_truth:` 属性加载规则。
4. **离线优先与渐进增强**: 100% 支持纯 Python 本地零依赖离线打分；检测到 LangFuse 环境时支持可选的 Post-MVP 轨迹同步。

---

## 2. 系统架构与模块划分

```
                          Scenario YAML (含 ground_truth 节)
                                         │
                                         ▼
                               [ EvaluatorEngine ]
                                         │  (读取 BlackboardState & GroundTruth)
        ┌───────────────────────┬────────┴───────────────┬───────────────────────┐
        ▼                       ▼                        ▼                       ▼
[ RootCauseEvaluator ] [ PathRecallEvaluator ]  [ AntiHallucinationEvaluator ] [ EfficiencyEvaluator ]
(权重 40%)             (权重 25%)               (权重 25%)                  (权重 10%)
        │                       │                        │                       │
        └───────────────────────┴────────┬───────────────┴───────────────────────┘
                                         ▼
                              [ EvaluationScorecard ]
                             (综合得分 0-100, 可配置 threshold)
                                         │
                         ┌───────────────┴───────────────┐
                         ▼                               ▼
                 [ 本地 Markdown/JSON 报告 ]     [ (Post-MVP) LangFuse Trace ]
```

---

## 3. Schema 详细定义 (`evaluator/schema.py`)

```python
from typing import Any, Literal
from pydantic import BaseModel, Field
from simulator.scenario import Scenario


class TimelineEvent(BaseModel):
    """强类型的 Ground Truth 时间线锚点事件。"""
    tick: int
    entity_id: str
    metric_name: str | None = None
    expected_value: float | None = None
    log_keyword: str | None = None
    description: str = ""


class GroundTruth(BaseModel):
    """故障剧本声明或独立配置的标准答案。"""
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
        """从 Scenario 实例及其 raw_data 中提取 ground_truth 节。"""
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
    """单项评测维度的得分与明细。"""
    dimension: Literal["root_cause", "path_recall", "anti_hallucination", "efficiency"]
    raw_score: float  # 0.0 - 1.0
    weight: float     # 权重，如 0.40
    weighted_score: float  # raw_score * weight * 100
    details: dict[str, Any] = Field(default_factory=dict)


class EvaluationScorecard(BaseModel):
    """评估总记分卡。"""
    scenario_name: str
    root_cause_score: DimensionScore
    path_recall_score: DimensionScore
    anti_hallucination_score: DimensionScore
    efficiency_score: DimensionScore
    total_score: float  # 0.0 - 100.0
    pass_threshold: float = 60.0
    status: Literal["PASSED", "FAILED"]  # total_score >= pass_threshold
    summary: str
```

---

## 4. 评估算法与防崩溃规则

### 4.1 根因准确率 (`RootCauseEvaluator` - 40% 权重)
1. **Entity 匹配 (60% 子权重)**:
   * 若 `report.root_cause_entity == gt.root_cause_entity`，得 1.0 分。
   * 否则若 `gt.root_cause_service` 在 `report.root_cause_entity` 中，得 0.6 分。
2. **Failure Type 匹配 (40% 子权重)**:
   * 不区分大小写匹配。如 `REDIS_LEAK` 与 `REDIS_POOL_LEAK` 子串匹配得 1.0 分。
3. **置信度加权**: Final Score = $(0.6 \times S_{\text{entity}} + 0.4 \times S_{\text{type}}) \times \text{clamp}(\text{report.confidence}, 0.0, 1.0)$。

### 4.2 路径召回率 (`PathRecallEvaluator` - 25% 权重)
分析 `BlackboardState["messages"]` 中的 `AIMessage.tool_calls`：
* **防除零防护**: 若 `gt.expected_tools` 为空，且实际未调用工具，得分记 1.0 分。
* 计算 Tool & Service 覆盖率的 $F_1$ 值: $F_1 = \frac{2 \cdot P \cdot R}{P + R}$。

### 4.3 抗幻觉打假 (`AntiHallucinationEvaluator` - 25% 权重)
校验 `BlackboardState["evidences"]` 中的 `Evidence` 实例：
* **核验源**: 与 `GroundTruth.timeline` 锚点及 `Projections` 时序快照比对。
* **时间戳容差**: $|T_{\text{evidence}} - T_{\text{event}}| \le 5.0\text{s}$ ($\pm 50$ Ticks)。
* **数值容差**: 指标数值相对误差 $\frac{|V_{\text{agent}} - V_{\text{real}}|}{V_{\text{real}}} \le 10\%$。
* **空证据兜底**: 若无 Evidence 提交，`anti_hallucination_score` 为 0.0。

### 4.4 资源效率 (`EfficiencyEvaluator` - 10% 权重)
* **防除零防护**: `safe_max_rounds = max(1, state.get("max_rounds", 5))`。
* 轮次得分: $1.0 - \frac{\text{current\_round} - 1}{\text{safe\_max\_rounds}}$。

---

## 5. 部署与测试集成

1. **E2E 演示脚本 (`run_eval_demo.py`)**: 全链路演示（Simulator 注入 -> Runtime 诊断 -> Evaluator 打分 -> 输出控制台记分卡与 Markdown 报告）。
2. **Post-MVP 渐进增强**: LangFuse 上报封装在 `try...except ImportError` 中。
3. **测试驱动 (TDD)**: 在 `tests/evaluator/` 编写单元测试，覆盖正常、边界及防崩溃逻辑。
