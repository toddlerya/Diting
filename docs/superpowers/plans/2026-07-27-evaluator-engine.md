# Evaluation Engine (Day 6 评估引擎) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 Diting (谛听) 项目的 `evaluator/` 模块，构建基于确定性断言与规则的比对引擎，对 Agent Runtime 输出的 `BlackboardState` 和 `DiagnosisReport` 进行根因准确率、路径召回率、抗幻觉真实度及资源效率四大维度的 0-100 分综合 Benchmark 自动化评估。

**Architecture:** `EvaluatorEngine` 作为主入口，解析含有 `ground_truth:` 信息的 `Scenario` YAML 得到强类型 `GroundTruth`，随后分别调用 `RootCauseEvaluator` (40%)、`PathRecallEvaluator` (25%)、`AntiHallucinationEvaluator` (25%) 与 `EfficiencyEvaluator` (10%) 计算单项 `DimensionScore`，合成 `EvaluationScorecard` 并判断 `status: PASSED | FAILED`。

**Tech Stack:** Python 3.13, Pydantic v2, Pytest, Ruff.

## Global Constraints

- **Python 版本**: `>= 3.13`（通过 `uv` 管理）。
- **指令执行**: 所有 Python 相关命令必须使用 `uv run` 引导。
- **代码质量约束**: 遵循 Ruff & Pytest 工作流：`uv run ruff check --fix .`、`uv run ruff format .`、`uv run pytest`。
- **时区标准**: ISO 8601 UTC 时间字符串，显式携带 `+00:00` 后缀。
- **强类型 Schema**: 所有数据结构必须通过 Pydantic v2 校验。

---

### Task 1: Ground Truth Schema 与 Scenario 支持

**Files:**
- Create: `evaluator/__init__.py`
- Create: `evaluator/schema.py`
- Modify: `simulator/scenario.py`
- Create: `tests/evaluator/__init__.py`
- Create: `tests/evaluator/test_schema.py`

**Interfaces:**
- Consumes: Pydantic v2, `simulator.scenario.Scenario`
- Produces: `TimelineEvent`, `GroundTruth`, `DimensionScore`, `EvaluationScorecard`

- [ ] **Step 1: 编写 Schema 的失败测试**

```python
# tests/evaluator/test_schema.py
import pytest
from evaluator.schema import (
    TimelineEvent,
    GroundTruth,
    DimensionScore,
    EvaluationScorecard,
)
from simulator.scenario import Scenario

def test_timeline_event_creation():
    event = TimelineEvent(
        tick=15,
        entity_id="Node-1",
        metric_name="disk_util",
        expected_value=0.96,
        log_keyword="Disk utility threshold exceeded",
    )
    assert event.tick == 15
    assert event.expected_value == 0.96

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
    sc = Scenario.from_dict(data) if hasattr(Scenario, "from_dict") else Scenario("test_scenario", "desc", [], seed=42)
    sc.ground_truth_data = data["ground_truth"]
    gt = GroundTruth.from_scenario(sc)
    assert gt.root_cause_service == "PaymentService"
    assert gt.failure_type == "REDIS_POOL_LEAK"
    assert len(gt.timeline) == 1
    assert gt.timeline[0].log_keyword == "Timeout waiting for connection"

def test_evaluation_scorecard_status():
    dim_rc = DimensionScore(dimension="root_cause", raw_score=1.0, weight=0.4, weighted_score=40.0)
    dim_pr = DimensionScore(dimension="path_recall", raw_score=1.0, weight=0.25, weighted_score=25.0)
    dim_ah = DimensionScore(dimension="anti_hallucination", raw_score=1.0, weight=0.25, weighted_score=25.0)
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
        summary="Perfect score"
    )
    assert card.status == "PASSED"
```

- [ ] **Step 2: 运行测试验证失败**

运行：`uv run pytest tests/evaluator/test_schema.py`
预期：失败，提示 `ModuleNotFoundError: No module named 'evaluator'`。

- [ ] **Step 3: 修改 `simulator/scenario.py` 保存原 JSON/YAML 数据**

在 `simulator/scenario.py` 的 `from_yaml` 中，将解析到的 `data.get("ground_truth", {})` 保存到 `scenario.ground_truth_data` 属性。

```python
# simulator/scenario.py
class Scenario:
    def __init__(self, name: str, description: str, steps: list[dict[str, Any]], seed: int = 42, ground_truth_data: dict[str, Any] | None = None):
        self.name = name
        self.description = description
        self.steps = steps
        self.seed = seed
        self.ground_truth_data = ground_truth_data or {}
```

- [ ] **Step 4: 实现 `evaluator/schema.py`**

```python
# evaluator/schema.py
from typing import Any, Literal
from pydantic import BaseModel, Field
from simulator.scenario import Scenario


class TimelineEvent(BaseModel):
    tick: int
    entity_id: str
    metric_name: str | None = None
    expected_value: float | None = None
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
```

- [ ] **Step 5: 运行测试验证通过**

运行：`uv run pytest tests/evaluator/test_schema.py`
预期：测试通过。

- [ ] **Step 6: 提交 Git**

```bash
git add evaluator/ __init__.py evaluator/schema.py simulator/scenario.py tests/evaluator/__init__.py tests/evaluator/test_schema.py
git commit -m "feat(evaluator): add GroundTruth and EvaluationScorecard schemas"
```

---

### Task 2: Root Cause Evaluator (`evaluator/root_cause.py`)

**Files:**
- Create: `evaluator/root_cause.py`
- Create: `tests/evaluator/test_root_cause.py`

**Interfaces:**
- Consumes: `runtime.schema.DiagnosisReport`, `evaluator.schema.GroundTruth`
- Produces: `RootCauseEvaluator.evaluate(report, ground_truth) -> DimensionScore`

- [ ] **Step 1: 编写 Root Cause Evaluator 的失败测试**

```python
# tests/evaluator/test_root_cause.py
import pytest
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
    # Entity score: 0.6, type score: 1.0, total raw: (0.6*0.6 + 0.4*1.0) * 0.8 = (0.36+0.4)*0.8 = 0.608
    assert abs(score.raw_score - 0.608) < 1e-4
```

- [ ] **Step 2: 运行测试验证失败**

运行：`uv run pytest tests/evaluator/test_root_cause.py`
预期：失败，提示 `ModuleNotFoundError: No module named 'evaluator.root_cause'`。

- [ ] **Step 3: 实现 `evaluator/root_cause.py`**

```python
# evaluator/root_cause.py
from evaluator.schema import DimensionScore, GroundTruth
from runtime.schema import DiagnosisReport


class RootCauseEvaluator:
    WEIGHT = 0.40

    def evaluate(self, report: DiagnosisReport | None, gt: GroundTruth) -> DimensionScore:
        if not report:
            return DimensionScore(
                dimension="root_cause",
                raw_score=0.0,
                weight=self.WEIGHT,
                weighted_score=0.0,
                details={"reason": "No diagnosis report provided"},
            )

        # 1. Entity Match (60% sub-weight)
        entity_score = 0.0
        if report.root_cause_entity == gt.root_cause_entity:
            entity_score = 1.0
        elif gt.root_cause_service and gt.root_cause_service.lower() in report.root_cause_entity.lower():
            entity_score = 0.6

        # 2. Failure Type Match (40% sub-weight)
        type_score = 0.0
        r_type = report.failure_type.lower().replace("_", "")
        gt_type = gt.failure_type.lower().replace("_", "")
        if r_type and (r_type in gt_type or gt_type in r_type):
            type_score = 1.0

        confidence = max(0.0, min(1.0, report.confidence))
        raw_score = (0.6 * entity_score + 0.4 * type_score) * confidence
        weighted_score = raw_score * self.WEIGHT * 100.0

        return DimensionScore(
            dimension="root_cause",
            raw_score=raw_score,
            weight=self.WEIGHT,
            weighted_score=weighted_score,
            details={
                "entity_score": entity_score,
                "type_score": type_score,
                "confidence": confidence,
                "predicted_entity": report.root_cause_entity,
                "actual_entity": gt.root_cause_entity,
                "predicted_type": report.failure_type,
                "actual_type": gt.failure_type,
            },
        )
```

- [ ] **Step 4: 运行测试验证通过**

运行：`uv run pytest tests/evaluator/test_root_cause.py`
预期：测试通过。

- [ ] **Step 5: 提交 Git**

```bash
git add evaluator/root_cause.py tests/evaluator/test_root_cause.py
git commit -m "feat(evaluator): implement RootCauseEvaluator"
```

---

### Task 3: Path Recall Evaluator (`evaluator/path_recall.py`)

**Files:**
- Create: `evaluator/path_recall.py`
- Create: `tests/evaluator/test_path_recall.py`

**Interfaces:**
- Consumes: `runtime.schema.BlackboardState`, `evaluator.schema.GroundTruth`
- Produces: `PathRecallEvaluator.evaluate(state, ground_truth) -> DimensionScore`

- [ ] **Step 1: 编写 Path Recall Evaluator 的失败测试**

```python
# tests/evaluator/test_path_recall.py
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
            {"name": "query_metrics", "args": {"entity_id": "Gateway"}},
            {"name": "query_logs", "args": {"service": "PaymentService"}},
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
```

- [ ] **Step 2: 运行测试验证失败**

运行：`uv run pytest tests/evaluator/test_path_recall.py`
预期：失败，提示 `ModuleNotFoundError: No module named 'evaluator.path_recall'`。

- [ ] **Step 3: 实现 `evaluator/path_recall.py`**

```python
# evaluator/path_recall.py
from langchain_core.messages import AIMessage
from evaluator.schema import DimensionScore, GroundTruth
from runtime.schema import BlackboardState


class PathRecallEvaluator:
    WEIGHT = 0.25

    def evaluate(self, state: BlackboardState, gt: GroundTruth) -> DimensionScore:
        actual_tools = set()
        actual_services = set()

        for msg in state.get("messages", []):
            if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls"):
                for tc in msg.tool_calls:
                    actual_tools.add(tc.get("name"))
                    args = tc.get("args", {})
                    if "entity_id" in args:
                        actual_services.add(args["entity_id"])
                    if "service" in args:
                        actual_services.add(args["service"])

        expected_tools = set(gt.expected_tools)
        expected_services = set(gt.expected_services)

        # Tool Recall & Precision
        if not expected_tools:
            tool_score = 1.0 if not actual_tools else 0.5
        else:
            tp_tools = len(actual_tools.intersection(expected_tools))
            tool_recall = tp_tools / len(expected_tools)
            tool_precision = tp_tools / len(actual_tools) if actual_tools else 0.0
            tool_score = (
                2 * tool_precision * tool_recall / (tool_precision + tool_recall)
                if (tool_precision + tool_recall) > 0
                else 0.0
            )

        # Service Recall & Precision
        if not expected_services:
            svc_score = 1.0 if not actual_services else 0.5
        else:
            tp_svc = len(actual_services.intersection(expected_services))
            svc_recall = tp_svc / len(expected_services)
            svc_precision = tp_svc / len(actual_services) if actual_services else 0.0
            svc_score = (
                2 * svc_precision * svc_recall / (svc_precision + svc_recall)
                if (svc_precision + svc_recall) > 0
                else 0.0
            )

        raw_score = 0.5 * tool_score + 0.5 * svc_score
        weighted_score = raw_score * self.WEIGHT * 100.0

        return DimensionScore(
            dimension="path_recall",
            raw_score=raw_score,
            weight=self.WEIGHT,
            weighted_score=weighted_score,
            details={
                "tool_score": tool_score,
                "service_score": svc_score,
                "actual_tools": list(actual_tools),
                "expected_tools": list(expected_tools),
                "actual_services": list(actual_services),
                "expected_services": list(expected_services),
            },
        )
```

- [ ] **Step 4: 运行测试验证通过**

运行：`uv run pytest tests/evaluator/test_path_recall.py`
预期：测试通过。

- [ ] **Step 5: 提交 Git**

```bash
git add evaluator/path_recall.py tests/evaluator/test_path_recall.py
git commit -m "feat(evaluator): implement PathRecallEvaluator"
```

---

### Task 4: Anti-Hallucination Evaluator (`evaluator/anti_hallucination.py`)

**Files:**
- Create: `evaluator/anti_hallucination.py`
- Create: `tests/evaluator/test_anti_hallucination.py`

**Interfaces:**
- Consumes: `runtime.schema.BlackboardState`, `evaluator.schema.GroundTruth`
- Produces: `AntiHallucinationEvaluator.evaluate(state, ground_truth) -> DimensionScore`

- [ ] **Step 1: 编写 Anti-Hallucination Evaluator 的失败测试**

```python
# tests/evaluator/test_anti_hallucination.py
import pytest
from evaluator.anti_hallucination import AntiHallucinationEvaluator
from evaluator.schema import GroundTruth, TimelineEvent
from runtime.schema import BlackboardState, Evidence

def test_anti_hallucination_valid_evidence():
    gt = GroundTruth(
        scenario_name="redis_leak",
        root_cause_service="PaymentService",
        root_cause_entity="PaymentService-RedisPool",
        failure_type="REDIS_POOL_LEAK",
        timeline=[
            TimelineEvent(tick=10, entity_id="PaymentService", log_keyword="Timeout waiting for connection")
        ],
    )
    ev = Evidence(
        id="ev-1",
        source="log",
        entity_id="PaymentService",
        timestamp="2026-07-27T00:00:00+00:00",
        summary="Timeout waiting for connection after 500ms",
    )
    state: BlackboardState = {
        "messages": [],
        "incident_alert": {},
        "suspect_entities": [],
        "evidences": [ev],
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

def test_anti_hallucination_empty_evidences():
    gt = GroundTruth(
        scenario_name="test",
        root_cause_service="S1",
        root_cause_entity="E1",
        failure_type="F1",
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
```

- [ ] **Step 2: 运行测试验证失败**

运行：`uv run pytest tests/evaluator/test_anti_hallucination.py`
预期：失败，提示 `ModuleNotFoundError: No module named 'evaluator.anti_hallucination'`。

- [ ] **Step 3: 实现 `evaluator/anti_hallucination.py`**

```python
# evaluator/anti_hallucination.py
from evaluator.schema import DimensionScore, GroundTruth
from runtime.schema import BlackboardState


class AntiHallucinationEvaluator:
    WEIGHT = 0.25

    def evaluate(self, state: BlackboardState, gt: GroundTruth) -> DimensionScore:
        evidences = state.get("evidences", [])
        if not evidences:
            return DimensionScore(
                dimension="anti_hallucination",
                raw_score=0.0,
                weight=self.WEIGHT,
                weighted_score=0.0,
                details={"reason": "No evidence provided in blackboard state"},
            )

        valid_count = 0
        total_count = len(evidences)
        details_list = []

        for ev in evidences:
            is_valid = False
            # Check against timeline events
            for te in gt.timeline:
                if te.entity_id.lower() in ev.entity_id.lower() or ev.entity_id.lower() in te.entity_id.lower():
                    # Keyword check
                    if te.log_keyword and te.log_keyword.lower() in ev.summary.lower():
                        is_valid = True
                        break
                    if te.metric_name and te.metric_name.lower() in ev.summary.lower():
                        is_valid = True
                        break

            # Fallback heuristic: If evidence contains non-empty valid summary and entity_id
            if not is_valid and ev.entity_id and ev.summary and ev.relevance_score >= 0.5:
                is_valid = True

            if is_valid:
                valid_count += 1
            details_list.append({"evidence_id": ev.id, "is_valid": is_valid, "summary": ev.summary})

        raw_score = valid_count / total_count if total_count > 0 else 0.0
        weighted_score = raw_score * self.WEIGHT * 100.0

        return DimensionScore(
            dimension="anti_hallucination",
            raw_score=raw_score,
            weight=self.WEIGHT,
            weighted_score=weighted_score,
            details={
                "valid_count": valid_count,
                "total_count": total_count,
                "evidences_detail": details_list,
            },
        )
```

- [ ] **Step 4: 运行测试验证通过**

运行：`uv run pytest tests/evaluator/test_anti_hallucination.py`
预期：测试通过。

- [ ] **Step 5: 提交 Git**

```bash
git add evaluator/anti_hallucination.py tests/evaluator/test_anti_hallucination.py
git commit -m "feat(evaluator): implement AntiHallucinationEvaluator"
```

---

### Task 5: Efficiency Evaluator (`evaluator/efficiency.py`)

**Files:**
- Create: `evaluator/efficiency.py`
- Create: `tests/evaluator/test_efficiency.py`

**Interfaces:**
- Consumes: `runtime.schema.BlackboardState`, `evaluator.schema.GroundTruth`
- Produces: `EfficiencyEvaluator.evaluate(state, ground_truth) -> DimensionScore`

- [ ] **Step 1: 编写 Efficiency Evaluator 的失败测试**

```python
# tests/evaluator/test_efficiency.py
import pytest
from evaluator.efficiency import EfficiencyEvaluator
from evaluator.schema import GroundTruth
from runtime.schema import BlackboardState

def test_efficiency_evaluation():
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
```

- [ ] **Step 2: 运行测试验证失败**

运行：`uv run pytest tests/evaluator/test_efficiency.py`
预期：失败，提示 `ModuleNotFoundError: No module named 'evaluator.efficiency'`。

- [ ] **Step 3: 实现 `evaluator/efficiency.py`**

```python
# evaluator/efficiency.py
from evaluator.schema import DimensionScore, GroundTruth
from runtime.schema import BlackboardState


class EfficiencyEvaluator:
    WEIGHT = 0.10

    def evaluate(self, state: BlackboardState, gt: GroundTruth) -> DimensionScore:
        current_round = state.get("current_round", 1)
        max_rounds = max(1, state.get("max_rounds", 5))

        round_penalty = (current_round - 1) / max_rounds
        raw_score = max(0.0, 1.0 - round_penalty)
        weighted_score = raw_score * self.WEIGHT * 100.0

        return DimensionScore(
            dimension="efficiency",
            raw_score=raw_score,
            weight=self.WEIGHT,
            weighted_score=weighted_score,
            details={
                "current_round": current_round,
                "max_rounds": max_rounds,
                "round_penalty": round_penalty,
            },
        )
```

- [ ] **Step 4: 运行测试验证通过**

运行：`uv run pytest tests/evaluator/test_efficiency.py`
预期：测试通过。

- [ ] **Step 5: 提交 Git**

```bash
git add evaluator/efficiency.py tests/evaluator/test_efficiency.py
git commit -m "feat(evaluator): implement EfficiencyEvaluator"
```

---

### Task 6: Evaluator Engine 主类与 Post-MVP 渐进增强 (`evaluator/engine.py`)

**Files:**
- Create: `evaluator/engine.py`
- Create: `tests/evaluator/test_engine.py`

**Interfaces:**
- Consumes: `evaluator.schema.*`, `runtime.schema.BlackboardState`
- Produces: `EvaluatorEngine.evaluate(state, scenario) -> EvaluationScorecard`

- [ ] **Step 1: 编写 EvaluatorEngine 的失败测试**

```python
# tests/evaluator/test_engine.py
import pytest
from evaluator.engine import EvaluatorEngine
from evaluator.schema import EvaluationScorecard
from runtime.schema import BlackboardState, DiagnosisReport
from simulator.scenario import Scenario

def test_evaluator_engine_full_flow():
    sc_data = {
        "name": "redis_leak_scenario",
        "description": "Redis leak test",
        "ground_truth": {
            "root_cause_service": "PaymentService",
            "root_cause_entity": "PaymentService-RedisPool",
            "failure_type": "REDIS_POOL_LEAK",
            "expected_tools": ["query_metrics"],
            "expected_services": ["PaymentService"],
        },
        "steps": [],
    }
    sc = Scenario("redis_leak_scenario", "Redis leak test", [], seed=42, ground_truth_data=sc_data["ground_truth"])
    report = DiagnosisReport(
        root_cause_entity="PaymentService-RedisPool",
        failure_type="REDIS_POOL_LEAK",
        confidence=1.0,
        evidence_ids=[],
        summary="Redis pool leaked",
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
        "diagnosis_report": report,
        "status": "COMPLETED",
    }
    engine = EvaluatorEngine(pass_threshold=60.0)
    scorecard = engine.evaluate(state, sc)

    assert isinstance(scorecard, EvaluationScorecard)
    assert scorecard.root_cause_score.raw_score == 1.0
    assert scorecard.total_score >= 60.0
    assert scorecard.status == "PASSED"
```

- [ ] **Step 2: 运行测试验证失败**

运行：`uv run pytest tests/evaluator/test_engine.py`
预期：失败，提示 `ModuleNotFoundError: No module named 'evaluator.engine'`。

- [ ] **Step 3: 实现 `evaluator/engine.py`**

```python
# evaluator/engine.py
import os
from typing import Any
from evaluator.anti_hallucination import AntiHallucinationEvaluator
from evaluator.efficiency import EfficiencyEvaluator
from evaluator.path_recall import PathRecallEvaluator
from evaluator.root_cause import RootCauseEvaluator
from evaluator.schema import EvaluationScorecard, GroundTruth
from runtime.schema import BlackboardState
from simulator.scenario import Scenario


class EvaluatorEngine:
    def __init__(self, pass_threshold: float = 60.0):
        self.pass_threshold = pass_threshold
        self.root_cause_eval = RootCauseEvaluator()
        self.path_recall_eval = PathRecallEvaluator()
        self.anti_hallucination_eval = AntiHallucinationEvaluator()
        self.efficiency_eval = EfficiencyEvaluator()

    def evaluate(self, state: BlackboardState, scenario: Scenario) -> EvaluationScorecard:
        gt = GroundTruth.from_scenario(scenario)
        report = state.get("diagnosis_report")

        rc_score = self.root_cause_eval.evaluate(report, gt)
        pr_score = self.path_recall_eval.evaluate(state, gt)
        ah_score = self.anti_hallucination_eval.evaluate(state, gt)
        eff_score = self.efficiency_eval.evaluate(state, gt)

        total_score = (
            rc_score.weighted_score
            + pr_score.weighted_score
            + ah_score.weighted_score
            + eff_score.weighted_score
        )

        status = "PASSED" if total_score >= self.pass_threshold else "FAILED"
        summary = (
            f"Benchmark Scorecard for {scenario.name}: Total Score = {total_score:.1f}/100 "
            f"(Status: {status}). Root Cause: {rc_score.raw_score * 100:.0f}%, "
            f"Path Recall: {pr_score.raw_score * 100:.0f}%, "
            f"Anti-Hallucination: {ah_score.raw_score * 100:.0f}%, "
            f"Efficiency: {eff_score.raw_score * 100:.0f}%."
        )

        scorecard = EvaluationScorecard(
            scenario_name=scenario.name,
            root_cause_score=rc_score,
            path_recall_score=pr_score,
            anti_hallucination_score=ah_score,
            efficiency_score=eff_score,
            total_score=round(total_score, 2),
            pass_threshold=self.pass_threshold,
            status=status,
            summary=summary,
        )

        # Post-MVP: LangFuse Progressive Enhancement
        self._maybe_log_langfuse(scorecard)

        return scorecard

    def _maybe_log_langfuse(self, scorecard: EvaluationScorecard) -> None:
        """若存在 LangFuse API key，可选进行轨迹与得分同步。"""
        if os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
            try:
                # Placeholder for optional LangFuse client log
                pass
            except ImportError:
                pass
```

- [ ] **Step 4: 运行测试验证通过**

运行：`uv run pytest tests/evaluator/test_engine.py`
预期：测试通过。

- [ ] **Step 5: 提交 Git**

```bash
git add evaluator/engine.py tests/evaluator/test_engine.py
git commit -m "feat(evaluator): assemble EvaluatorEngine with threshold and scorecard generation"
```

---

### Task 7: E2E 演示脚本与全量 Ruff / Pytest 验证

**Files:**
- Create: `run_eval_demo.py`
- Modify: `README.md`
- Test: 全量 pytest 测试集与 Ruff 检查

- [ ] **Step 1: 实现 `run_eval_demo.py` 全链路 E2E 脚本**

```python
# run_eval_demo.py
import json
from evaluator.engine import EvaluatorEngine
from runtime.graph import run_diagnosis_workflow
from simulator.scenario import Scenario


def main():
    print("=" * 60)
    print("🐕 Diting (谛听) - Day 6 Evaluation Engine E2E Demo")
    print("=" * 60)

    # 1. 加载包含 Ground Truth 的故障剧本
    sc_data = {
        "name": "payment_redis_exhaust_cascade",
        "description": "PaymentService Redis Connection Pool Exhaustion Cascade Failure",
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
    scenario = Scenario("payment_redis_exhaust_cascade", "PaymentService Redis Leak", [], seed=42, ground_truth_data=sc_data["ground_truth"])

    # 2. 模拟 Firing Alert 触发展开 LangGraph 故障诊断
    alert = {
        "alert_name": "HighServiceLatency",
        "service": "Gateway",
        "severity": "CRITICAL",
    }
    print("\n[1/3] Running LangGraph Multi-Agent Diagnosis Workflow...")
    final_state = run_diagnosis_workflow(alert, thread_id="eval-demo-thread")

    print("\n[2/3] Diagnosis Completed. Report Summary:")
    report = final_state.get("diagnosis_report")
    if report:
        print(f"  - Root Cause Entity : {report.root_cause_entity}")
        print(f"  - Failure Type      : {report.failure_type}")
        print(f"  - Confidence Score  : {report.confidence:.2f}")

    # 3. 运行 EvaluatorEngine 自动化打分
    print("\n[3/3] Running EvaluatorEngine Benchmark Evaluation...")
    engine = EvaluatorEngine(pass_threshold=60.0)
    scorecard = engine.evaluate(final_state, scenario)

    print("\n" + "=" * 60)
    print("📊 BENCHMARK EVALUATION SCORECARD")
    print("=" * 60)
    print(f"Scenario Name       : {scorecard.scenario_name}")
    print(f"Total Benchmark Score: {scorecard.total_score:.1f} / 100.0")
    print(f"Evaluation Status   : {scorecard.status}")
    print("-" * 60)
    print(f"  - Root Cause (40%) : {scorecard.root_cause_score.weighted_score:.1f} pts (Raw: {scorecard.root_cause_score.raw_score * 100:.0f}%)")
    print(f"  - Path Recall (25%): {scorecard.path_recall_score.weighted_score:.1f} pts (Raw: {scorecard.path_recall_score.raw_score * 100:.0f}%)")
    print(f"  - Anti-Hallucination(25%): {scorecard.anti_hallucination_score.weighted_score:.1f} pts (Raw: {scorecard.anti_hallucination_score.raw_score * 100:.0f}%)")
    print(f"  - Efficiency (10%) : {scorecard.efficiency_score.weighted_score:.1f} pts (Raw: {scorecard.efficiency_score.raw_score * 100:.0f}%)")
    print("=" * 60)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 运行全量单元测试与 E2E 演示**

运行：
1. `uv run python run_eval_demo.py`
2. `uv run pytest`

- [ ] **Step 3: 运行 Ruff 校验与格式化**

运行：
1. `uv run ruff check --fix .`
2. `uv run ruff format .`

- [ ] **Step 4: 提交 Git 并结束**

```bash
git add run_eval_demo.py README.md
git commit -m "feat(evaluator): complete Day 6 Evaluation Engine with run_eval_demo script"
```
