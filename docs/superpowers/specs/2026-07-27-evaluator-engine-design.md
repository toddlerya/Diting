# Diting (谛听) Evaluation Engine ( Day 6 评估引擎) 详细设计说明书

## 1. 概述与目标

Evaluation Engine (评估引擎) 是 Diting (谛听) 平台的 Day 6 核心模块，用于针对给定故障剧本 (Scenario) 的 Ground Truth，对 Agent Runtime 输出的结构化诊断报告 (`DiagnosisReport`) 和排查过程轨迹进行自动化、多维度的 Benchmark 打分。

### 核心目标
1. **多维自动化打分**: 涵盖根因准确率 (Root Cause Accuracy)、路径召回率 (Path Recall)、抗幻觉真实度 (Anti-Hallucination) 及资源效率 (Efficiency)。
2. **确定性与打假逻辑**: 对 Agent 输出的 Pydantic `Evidence` 证据链进行物理事实反查与三阶过滤（时间窗口容差 $\pm 5\text{s}$、数值相对误差 $\le 10\%$、日志关键字匹配）。
3. **离线优先与渐进增强**: 100% 支持纯 Python 本地零依赖离线打分，同时支持检测 LangFuse 环境变量自动上报可视化 Trace 与分数指标。

---

## 2. 系统架构与模块划分

```
                               Scenario YAML (Ground Truth)
                                            │
                                            ▼
                                  [ EvaluatorEngine ]
                                            │
        ┌───────────────────────┬───────────┴───────────┬───────────────────────┐
        ▼                       ▼                       ▼                       ▼
[ RootCauseEvaluator ] [ PathRecallEvaluator ] [ AntiHallucinationEvaluator ] [ EfficiencyEvaluator ]
(权重 40%)             (权重 25%)              (权重 25%)                  (权重 10%)
        │                       │                       │                       │
        └───────────────────────┴───────────┬───────────┴───────────────────────┘
                                            ▼
                                 [ EvaluationScorecard ]
                                    (综合得分 0-100)
                                            │
                            ┌───────────────┴───────────────┐
                            ▼                               ▼
                    [ 本地控制台 / Markdown ]       [ (可选) LangFuse Trace ]
```

### 目录结构与模块文件
* `evaluator/__init__.py`
* `evaluator/schema.py`: `GroundTruth`, `EvaluationScorecard` 及细粒度得分 Schema。
* `evaluator/root_cause.py`: 根因服务、实体与故障类型匹配计算器。
* `evaluator/path_recall.py`: 工具调用、涵盖服务与指标的 $F_1$ 路径召回计算器。
* `evaluator/anti_hallucination.py`: 基于真实物理投影数据的证据链打假校验器。
* `evaluator/efficiency.py`: 对话轮次与工具重复调用开销计算器。
* `evaluator/engine.py`: 评测引擎入口类 `EvaluatorEngine` 及 LangFuse 渐进增强接入。
* `run_eval_demo.py`: E2E 全流程评估示范脚本。
* `tests/evaluator/`: pytest 单元测试全覆盖。

---

## 3. Schema 详细定义 (`evaluator/schema.py`)

```python
from typing import Any, Literal
from pydantic import BaseModel, Field


class GroundTruth(BaseModel):
    """故障剧本声明或独立配置的标准答案。"""
    scenario_name: str
    root_cause_service: str
    root_cause_entity: str
    failure_type: str
    expected_tools: list[str] = Field(default_factory=list)
    expected_services: list[str] = Field(default_factory=list)
    expected_metrics: list[str] = Field(default_factory=list)
    timeline: list[dict[str, Any]] = Field(default_factory=list)


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
    status: Literal["PASSED", "FAILED"]  # total_score >= 60.0 判为 PASSED
    summary: str
```

---

## 4. 评估算法与规则说明

### 4.1 根因准确率 (`RootCauseEvaluator` - 40% 权重)
1. **Entity 匹配 (60% 子权重)**:
   * 若 `DiagnosisReport.root_cause_entity == GroundTruth.root_cause_entity`，得 1.0 分。
   * 否则若 `DiagnosisReport.root_cause_entity` 包含 `GroundTruth.root_cause_service`，得 0.6 分。
   * 否则得 0.0 分。
2. **Failure Type 匹配 (40% 子权重)**:
   * 采用不区分大小写的子串/语义匹配。如 `REDIS_POOL_LEAK` 与 `redis_leak` 包含匹配得 1.0 分。
3. **置信度衰减**: 最终 Raw Score = $(0.6 \times S_{\text{entity}} + 0.4 \times S_{\text{type}}) \times \text{report.confidence}$。

### 4.2 路径召回率 (`PathRecallEvaluator` - 25% 权重)
分析 `BlackboardState["messages"]` 中的 `AIMessage.tool_calls` / `ToolMessage` 集合：
* `Tool Precision & Recall`: 实际调用的 Tool 集合与 `expected_tools` 的交集比。
* `Service Precision & Recall`: 调用的参数中涵盖的实体/服务集合与 `expected_services` 的交集比。
* 计算综合 $F_1$ 值: $F_1 = \frac{2 \cdot P \cdot R}{P + R}$。

### 4.3 抗幻觉打假 (`AntiHallucinationEvaluator` - 25% 权重)
扫描 `BlackboardState["evidences"]` 中的各项 `Evidence`：
* **时间戳容差**: $|T_{\text{evidence}} - T_{\text{event}}| \le 5.0\text{s}$ ($\pm 50$ Ticks)。
* **数值容差**: 指标数值相对误差 $\frac{|V_{\text{agent}} - V_{\text{real}}|}{V_{\text{real}}} \le 10\%$。
* **日志与知识点文本**: 包含不区分大小写关键字。
* 结果: $\text{Raw Score} = \frac{\text{Valid Evidences Count}}{\text{Total Evidences Count}}$（若无 Evidence 输出则为 0.0）。

### 4.4 资源效率 (`EfficiencyEvaluator` - 10% 权重)
* 轮次扣分: $\text{Score}_{\text{round}} = 1.0 - \frac{\text{current\_round} - 1}{\text{max\_rounds}}$。
* Tool 重复扣分: 同一 Entity + Metric 被重复查询超 2 次，每次扣 0.1 分。

---

## 5. 零依赖与测试规范

1. **测试驱动 (TDD)**: 在 `tests/evaluator/` 编写单元测试，验证各种完美报告、瑕疵报告与严重幻觉报告的打分确定性。
2. **环境与质量规范**: 遵循 `AGENTS.md`，使用 `uv run pytest`、`uv run ruff check --fix .` 与 `uv run ruff format .`。
