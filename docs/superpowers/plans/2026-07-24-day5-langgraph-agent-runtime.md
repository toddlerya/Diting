# Day 5 LangGraph Multi-Agent Agent Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Day 5 `runtime/` module for Diting (谛听), creating a multi-agent blackboard collaboration workflow built on native LangGraph `StateGraph`, Pydantic v2 evidence schemas, parallel fan-out dispatch, and offline Mock LLM support.

**Architecture:** A central Supervisor Agent Node inspects the shared `BlackboardState` and issues parallel tool calls/routing (`next_steps: list[str]`) to Specialist Agent Node Wrappers (Metrics, Logs, Trace, Knowledge). Each Node Wrapper queries its corresponding MCP service, formats raw outputs into concise `Evidence` objects, and appends a `ToolMessage` to maintain message protocol validity. When evidence is complete, the flow transitions to `Synthesizer` to emit a structured `DiagnosisReport`.

**Tech Stack:** Python 3.13, LangGraph (`langgraph`), LangChain Core (`langchain-core`), Pydantic v2, FastAPI/httpx, Pytest, Ruff.

## Global Constraints

- **Python Version**: `>= 3.13` (managed via `uv`).
- **Command Execution**: All Python commands must use `uv run`.
- **Ruff & Pytest Workflow**: `uv run ruff check --fix .`, `uv run ruff format .`, `uv run pytest`.
- **Timezone Standard**: ISO 8601 UTC string ending with `+00:00`.
- **Strict Pydantic Schemas**: All data structures must validate with Pydantic v2.

---

### Task 1: Dependencies Setup & Environment Verification

**Files:**
- Modify: `pyproject.toml`
- Test: Run `uv sync` and check dependency loading

**Interfaces:**
- Consumes: `pyproject.toml`
- Produces: `langgraph`, `langchain-core`, `langchain-openai` installed in `.venv`

- [ ] **Step 1: Update pyproject.toml with LangGraph & LangChain dependencies**

Add `"langgraph>=0.2.70"`, `"langchain-core>=0.3.38"`, `"langchain-openai>=0.3.7"` to `pyproject.toml`.

- [ ] **Step 2: Sync dependencies with uv**

Run: `uv sync`
Expected: Successfully synced dependencies without errors.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build(deps): add langgraph and langchain dependencies for Day 5 runtime"
```

---

### Task 2: Pydantic Schemas & BlackboardState Reducer (`runtime/schema.py`)

**Files:**
- Create: `runtime/__init__.py`
- Create: `runtime/schema.py`
- Create: `tests/runtime/__init__.py`
- Create: `tests/runtime/test_schema.py`

**Interfaces:**
- Consumes: Pydantic v2, `langchain_core.messages.BaseMessage`
- Produces: `Evidence`, `DiagnosisReport`, `BlackboardState`

- [ ] **Step 1: Write failing test for schema and BlackboardState**

```python
# tests/runtime/test_schema.py
import pytest
from runtime.schema import Evidence, DiagnosisReport, BlackboardState

def test_evidence_creation():
    ev = Evidence(
        id="ev-1",
        source="metric",
        entity_id="order-service",
        timestamp="2026-07-24T00:00:00+00:00",
        summary="High CPU usage 95%",
        details={"cpu_util": 0.95}
    )
    assert ev.source == "metric"
    assert ev.timestamp.endswith("+00:00")

def test_diagnosis_report_creation():
    report = DiagnosisReport(
        root_cause_entity="order-service",
        failure_type="CPU_BURST",
        confidence=0.95,
        evidence_ids=["ev-1"],
        summary="Order service CPU spike caused crash",
        recommended_actions=["Scale up pod"]
    )
    assert report.confidence == 0.95

def test_blackboard_state_initialization():
    state: BlackboardState = {
        "messages": [],
        "incident_alert": {"alert_name": "HighLatency"},
        "suspect_entities": ["order-service"],
        "evidences": [],
        "matched_runbooks": [],
        "current_round": 1,
        "max_rounds": 5,
        "next_steps": ["MetricsNode"],
        "diagnosis_report": None,
        "status": "RUNNING"
    }
    assert state["status"] == "RUNNING"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/runtime/test_schema.py`
Expected: FAIL with ModuleNotFoundError or import error for `runtime.schema`.

- [ ] **Step 3: Implement runtime/schema.py**

```python
# runtime/schema.py
import operator
from typing import Annotated, Literal, TypedDict
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage


class Evidence(BaseModel):
    id: str
    source: Literal["metric", "log", "trace", "runbook"]
    entity_id: str
    timestamp: str  # ISO 8601 UTC string (+00:00)
    summary: str
    details: dict = Field(default_factory=dict)
    relevance_score: float = 1.0


class DiagnosisReport(BaseModel):
    root_cause_entity: str
    failure_type: str  # e.g., "CPU_BURST", "MEMORY_LEAK", "NETWORK_LATENCY"
    confidence: float  # 0.0 - 1.0
    evidence_ids: list[str]
    summary: str
    recommended_actions: list[str] = Field(default_factory=list)


class BlackboardState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]
    incident_alert: dict
    suspect_entities: list[str]
    evidences: Annotated[list[Evidence], operator.add]
    matched_runbooks: list[dict]
    current_round: int
    max_rounds: int
    next_steps: list[str]  # 并发派发节点列表，如 ["MetricsNode", "LogsNode"]
    diagnosis_report: DiagnosisReport | None
    status: Literal["RUNNING", "COMPLETED", "FAILED"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/runtime/test_schema.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add runtime/schema.py tests/runtime/test_schema.py runtime/__init__.py tests/runtime/__init__.py
git commit -m "feat(runtime): add BlackboardState and Pydantic Evidence schemas"
```

---

### Task 3: MCP Agent Tools Adapter with InjectedToolCallId & ToolMessage (`runtime/tools/mcp_tools.py`)

**Files:**
- Create: `runtime/tools/__init__.py`
- Create: `runtime/tools/mcp_tools.py`
- Create: `tests/runtime/test_mcp_tools.py`

**Interfaces:**
- Consumes: `runtime.schema.Evidence`, MCP server APIs (Prometheus, Loki, Trace, Knowledge)
- Produces: MCP Tool functions returning `(Evidence, ToolMessage)`

- [ ] **Step 1: Write failing test for MCP Agent Tools**

```python
# tests/runtime/test_mcp_tools.py
import pytest
from langchain_core.messages import ToolMessage
from runtime.tools.mcp_tools import (
    query_metrics_tool,
    query_logs_tool,
    query_trace_tool,
    query_knowledge_tool
)

def test_query_metrics_tool_mock():
    evidence, tool_msg = query_metrics_tool(
        entity_id="order-service",
        query="container_cpu_usage_seconds_total",
        tool_call_id="call_123"
    )
    assert evidence.source == "metric"
    assert evidence.entity_id == "order-service"
    assert isinstance(tool_msg, ToolMessage)
    assert tool_msg.tool_call_id == "call_123"

def test_query_logs_tool_mock():
    evidence, tool_msg = query_logs_tool(
        entity_id="order-service",
        query="Exception",
        tool_call_id="call_456"
    )
    assert evidence.source == "log"
    assert tool_msg.tool_call_id == "call_456"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/runtime/test_mcp_tools.py`
Expected: FAIL with ModuleNotFoundError or import error for `runtime.tools.mcp_tools`.

- [ ] **Step 3: Implement runtime/tools/mcp_tools.py**

```python
# runtime/tools/mcp_tools.py
import uuid
from datetime import datetime, timezone
from typing import Annotated
from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId
from runtime.schema import Evidence


def query_metrics_tool(
    entity_id: str,
    query: str,
    tool_call_id: Annotated[str, InjectedToolCallId] = ""
) -> tuple[Evidence, ToolMessage]:
    """查询 Prometheus 指标并生成 Evidence 与 ToolMessage。"""
    call_id = tool_call_id or f"call_{uuid.uuid4().hex[:8]}"
    summary = f"Prometheus query '{query}' for {entity_id}: detected CPU/memory spike"
    ev = Evidence(
        id=f"ev-metric-{uuid.uuid4().hex[:6]}",
        source="metric",
        entity_id=entity_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        summary=summary,
        details={"query": query, "metric_val": 92.5}
    )
    msg = ToolMessage(content=summary, tool_call_id=call_id)
    return ev, msg


def query_logs_tool(
    entity_id: str,
    query: str,
    tool_call_id: Annotated[str, InjectedToolCallId] = ""
) -> tuple[Evidence, ToolMessage]:
    """查询 Loki 日志并生成 Evidence 与 ToolMessage。"""
    call_id = tool_call_id or f"call_{uuid.uuid4().hex[:8]}"
    summary = f"Loki log query '{query}' for {entity_id}: found NullPointerException stack trace"
    ev = Evidence(
        id=f"ev-log-{uuid.uuid4().hex[:6]}",
        source="log",
        entity_id=entity_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        summary=summary,
        details={"query": query, "log_line": "ERROR java.lang.NullPointerException at OrderController.java:42"}
    )
    msg = ToolMessage(content=summary, tool_call_id=call_id)
    return ev, msg


def query_trace_tool(
    entity_id: str,
    trace_id: str,
    tool_call_id: Annotated[str, InjectedToolCallId] = ""
) -> tuple[Evidence, ToolMessage]:
    """查询 Trace 调用链并生成 Evidence 与 ToolMessage。"""
    call_id = tool_call_id or f"call_{uuid.uuid4().hex[:8]}"
    summary = f"Trace query '{trace_id}' for {entity_id}: span latency exceeded 2500ms"
    ev = Evidence(
        id=f"ev-trace-{uuid.uuid4().hex[:6]}",
        source="trace",
        entity_id=entity_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        summary=summary,
        details={"trace_id": trace_id, "duration_ms": 2540.0}
    )
    msg = ToolMessage(content=summary, tool_call_id=call_id)
    return ev, msg


def query_knowledge_tool(
    query: str,
    tool_call_id: Annotated[str, InjectedToolCallId] = ""
) -> tuple[Evidence, ToolMessage]:
    """检索 Knowledge 运维 Wiki 并生成 Evidence 与 ToolMessage。"""
    call_id = tool_call_id or f"call_{uuid.uuid4().hex[:8]}"
    summary = f"Knowledge base runbook search '{query}': Matched High CPU Runbook RB-102"
    ev = Evidence(
        id=f"ev-kb-{uuid.uuid4().hex[:6]}",
        source="runbook",
        entity_id="system",
        timestamp=datetime.now(timezone.utc).isoformat(),
        summary=summary,
        details={"runbook_id": "RB-102", "title": "High CPU Recovery Procedure"}
    )
    msg = ToolMessage(content=summary, tool_call_id=call_id)
    return ev, msg
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/runtime/test_mcp_tools.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add runtime/tools/mcp_tools.py tests/runtime/test_mcp_tools.py runtime/tools/__init__.py
git commit -m "feat(runtime): add MCP Agent tools with InjectedToolCallId and ToolMessage binding"
```

---

### Task 4: Specialist Node Wrappers & Offline Mock LLM Engine (`runtime/agents/` & `runtime/mock_llm.py`)

**Files:**
- Create: `runtime/mock_llm.py`
- Create: `runtime/agents/__init__.py`
- Create: `runtime/agents/supervisor.py`
- Create: `runtime/agents/metrics_agent.py`
- Create: `runtime/agents/logs_agent.py`
- Create: `runtime/agents/trace_agent.py`
- Create: `runtime/agents/knowledge_agent.py`
- Create: `runtime/agents/synthesizer.py`
- Create: `tests/runtime/test_agents.py`

**Interfaces:**
- Consumes: `BlackboardState`, `runtime.tools.mcp_tools`
- Produces: LangGraph Node functions returning `dict[str, Any]`

- [ ] **Step 1: Write failing test for Agent Node Wrappers and Mock LLM**

```python
# tests/runtime/test_agents.py
import pytest
from runtime.schema import BlackboardState
from runtime.mock_llm import MockLLMClient
from runtime.agents.supervisor import supervisor_node
from runtime.agents.metrics_agent import metrics_node
from runtime.agents.synthesizer import synthesizer_node

def test_mock_llm_multi_round_decisions():
    client = MockLLMClient()
    
    # Round 1 -> Parallel dispatch
    state1: BlackboardState = {
        "messages": [],
        "incident_alert": {"service": "order-service"},
        "suspect_entities": ["order-service"],
        "evidences": [],
        "matched_runbooks": [],
        "current_round": 1,
        "max_rounds": 5,
        "next_steps": [],
        "diagnosis_report": None,
        "status": "RUNNING"
    }
    resp1 = client.invoke(state1)
    assert set(resp1["next_steps"]) == {"MetricsNode", "LogsNode", "TraceNode", "KnowledgeNode"}

def test_metrics_node_wrapper():
    state: BlackboardState = {
        "messages": [],
        "incident_alert": {},
        "suspect_entities": ["order-service"],
        "evidences": [],
        "matched_runbooks": [],
        "current_round": 1,
        "max_rounds": 5,
        "next_steps": ["MetricsNode"],
        "diagnosis_report": None,
        "status": "RUNNING"
    }
    update = metrics_node(state)
    assert "evidences" in update
    assert "messages" in update
    assert len(update["evidences"]) == 1
    assert update["evidences"][0].source == "metric"

def test_synthesizer_node_wrapper():
    state: BlackboardState = {
        "messages": [],
        "incident_alert": {"service": "order-service"},
        "suspect_entities": ["order-service"],
        "evidences": [],
        "matched_runbooks": [],
        "current_round": 2,
        "max_rounds": 5,
        "next_steps": ["Synthesizer"],
        "diagnosis_report": None,
        "status": "RUNNING"
    }
    update = synthesizer_node(state)
    assert update["status"] == "COMPLETED"
    assert update["diagnosis_report"].root_cause_entity == "order-service"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/runtime/test_agents.py`
Expected: FAIL with ModuleNotFoundError or import error for `runtime.mock_llm` / `runtime.agents`.

- [ ] **Step 3: Implement runtime/mock_llm.py**

```python
# runtime/mock_llm.py
from typing import Any
from runtime.schema import BlackboardState, DiagnosisReport


class MockLLMClient:
    """按轮次返回确定性并发与定向 dispatch 决议的 Mock LLM。"""

    def invoke(self, state: BlackboardState) -> dict[str, Any]:
        curr_round = state.get("current_round", 1)
        if curr_round == 1:
            return {
                "next_steps": ["MetricsNode", "LogsNode", "TraceNode", "KnowledgeNode"],
                "suspect_entities": state.get("suspect_entities", ["order-service"])
            }
        elif curr_round == 2:
            return {
                "next_steps": ["LogsNode"],
                "suspect_entities": ["order-service"]
            }
        else:
            return {
                "next_steps": ["Synthesizer"]
            }
```

- [ ] **Step 4: Implement Agent Node Wrappers in runtime/agents/**

`runtime/agents/supervisor.py`:
```python
from typing import Any
from runtime.schema import BlackboardState
from runtime.mock_llm import MockLLMClient

def supervisor_node(state: BlackboardState) -> dict[str, Any]:
    client = MockLLMClient()
    decision = client.invoke(state)
    return {
        "next_steps": decision.get("next_steps", ["Synthesizer"]),
        "current_round": state.get("current_round", 1) + 1
    }
```

`runtime/agents/metrics_agent.py`:
```python
from typing import Any
from runtime.schema import BlackboardState
from runtime.tools.mcp_tools import query_metrics_tool

def metrics_node(state: BlackboardState) -> dict[str, Any]:
    entities = state.get("suspect_entities", ["system"])
    target = entities[0] if entities else "system"
    ev, msg = query_metrics_tool(entity_id=target, query="container_cpu_usage_seconds_total")
    return {
        "evidences": [ev],
        "messages": [msg]
    }
```

`runtime/agents/logs_agent.py`:
```python
from typing import Any
from runtime.schema import BlackboardState
from runtime.tools.mcp_tools import query_logs_tool

def logs_node(state: BlackboardState) -> dict[str, Any]:
    entities = state.get("suspect_entities", ["system"])
    target = entities[0] if entities else "system"
    ev, msg = query_logs_tool(entity_id=target, query="Exception")
    return {
        "evidences": [ev],
        "messages": [msg]
    }
```

`runtime/agents/trace_agent.py`:
```python
from typing import Any
from runtime.schema import BlackboardState
from runtime.tools.mcp_tools import query_trace_tool

def trace_node(state: BlackboardState) -> dict[str, Any]:
    entities = state.get("suspect_entities", ["system"])
    target = entities[0] if entities else "system"
    ev, msg = query_trace_tool(entity_id=target, trace_id="tr-88902")
    return {
        "evidences": [ev],
        "messages": [msg]
    }
```

`runtime/agents/knowledge_agent.py`:
```python
from typing import Any
from runtime.schema import BlackboardState
from runtime.tools.mcp_tools import query_knowledge_tool

def knowledge_node(state: BlackboardState) -> dict[str, Any]:
    ev, msg = query_knowledge_tool(query="High CPU load troubleshooting")
    return {
        "evidences": [ev],
        "messages": [msg]
    }
```

`runtime/agents/synthesizer.py`:
```python
from typing import Any
from runtime.schema import BlackboardState, DiagnosisReport

def synthesizer_node(state: BlackboardState) -> dict[str, Any]:
    evidences = state.get("evidences", [])
    ev_ids = [e.id for e in evidences]
    entities = state.get("suspect_entities", ["unknown-service"])
    target = entities[0] if entities else "unknown-service"

    report = DiagnosisReport(
        root_cause_entity=target,
        failure_type="CPU_BURST",
        confidence=0.92,
        evidence_ids=ev_ids,
        summary=f"Incident root cause isolated to {target} due to CPU burst and exception stack trace.",
        recommended_actions=[f"Restart pod for {target}", "Apply CPU limit patch"]
    )
    return {
        "diagnosis_report": report,
        "status": "COMPLETED"
    }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/runtime/test_agents.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add runtime/mock_llm.py runtime/agents/ tests/runtime/test_agents.py
git commit -m "feat(runtime): implement Specialist Node Wrappers and Mock LLM Engine"
```

---

### Task 5: StateGraph Assembly & MemorySaver Checkpointer (`runtime/graph.py`)

**Files:**
- Create: `runtime/graph.py`
- Create: `tests/runtime/test_graph_workflow.py`

**Interfaces:**
- Consumes: All node functions in `runtime.agents`, `BlackboardState`, `langgraph.checkpoint.memory.MemorySaver`
- Produces: `build_diagnosis_graph()`, `run_diagnosis_workflow(alert_dict)`

- [ ] **Step 1: Write failing test for full LangGraph workflow execution**

```python
# tests/runtime/test_graph_workflow.py
import pytest
from runtime.graph import run_diagnosis_workflow

def test_full_diagnosis_workflow():
    alert = {
        "alert_name": "HighCpuUsage",
        "service": "order-service",
        "timestamp": "2026-07-24T00:00:00+00:00"
    }
    result = run_diagnosis_workflow(alert_dict=alert, thread_id="incident-test-001")
    assert result["status"] == "COMPLETED"
    assert result["diagnosis_report"] is not None
    assert result["diagnosis_report"].root_cause_entity == "order-service"
    assert len(result["evidences"]) >= 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/runtime/test_graph_workflow.py`
Expected: FAIL with ModuleNotFoundError or import error for `runtime.graph`.

- [ ] **Step 3: Implement runtime/graph.py**

```python
# runtime/graph.py
from typing import Any
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from runtime.agents.knowledge_agent import knowledge_node
from runtime.agents.logs_agent import logs_node
from runtime.agents.metrics_agent import metrics_node
from runtime.agents.supervisor import supervisor_node
from runtime.agents.synthesizer import synthesizer_node
from runtime.agents.trace_agent import trace_node
from runtime.schema import BlackboardState


def route_supervisor(state: BlackboardState) -> list[str]:
    """根据 Supervisor 输出的 next_steps 进行动态扇出条件路由。"""
    steps = state.get("next_steps", [])
    status = state.get("status", "RUNNING")
    curr_round = state.get("current_round", 1)
    max_rounds = state.get("max_rounds", 5)

    if status == "COMPLETED" or curr_round > max_rounds or "Synthesizer" in steps:
        return ["Synthesizer"]
    return steps if steps else ["Synthesizer"]


def build_diagnosis_graph():
    """构建原生的 LangGraph StateGraph，接入 MemorySaver Checkpointer。"""
    builder = StateGraph(BlackboardState)

    # 注册节点
    builder.add_node("Supervisor", supervisor_node)
    builder.add_node("MetricsNode", metrics_node)
    builder.add_node("LogsNode", logs_node)
    builder.add_node("TraceNode", trace_node)
    builder.add_node("KnowledgeNode", knowledge_node)
    builder.add_node("Synthesizer", synthesizer_node)

    # 设入口为 Supervisor
    builder.set_entry_point("Supervisor")

    # 条件边：Supervisor 按 next_steps 并行扇出到各 Specialist Nodes
    builder.add_conditional_edges(
        "Supervisor",
        route_supervisor,
        {
            "MetricsNode": "MetricsNode",
            "LogsNode": "LogsNode",
            "TraceNode": "TraceNode",
            "KnowledgeNode": "KnowledgeNode",
            "Synthesizer": "Synthesizer",
        },
    )

    # Specialist Nodes 执完后汇合交回 Supervisor
    builder.add_edge("MetricsNode", "Supervisor")
    builder.add_edge("LogsNode", "Supervisor")
    builder.add_edge("TraceNode", "Supervisor")
    builder.add_edge("KnowledgeNode", "Supervisor")

    # Synthesizer 诊断结束
    builder.add_edge("Synthesizer", END)

    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)


def run_diagnosis_workflow(alert_dict: dict[str, Any], thread_id: str = "incident-001") -> BlackboardState:
    """运行全流程微服务故障诊断。"""
    graph = build_diagnosis_graph()
    initial_state: BlackboardState = {
        "messages": [],
        "incident_alert": alert_dict,
        "suspect_entities": [alert_dict.get("service", "unknown-service")],
        "evidences": [],
        "matched_runbooks": [],
        "current_round": 1,
        "max_rounds": 5,
        "next_steps": [],
        "diagnosis_report": None,
        "status": "RUNNING",
    }
    config = {"configurable": {"thread_id": thread_id}}
    final_state = graph.invoke(initial_state, config=config)
    return final_state
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/runtime/test_graph_workflow.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add runtime/graph.py tests/runtime/test_graph_workflow.py
git commit -m "feat(runtime): assemble LangGraph StateGraph with parallel dispatch and MemorySaver checkpointer"
```

---

### Task 6: Full Verification & Ruff Code Quality Check

**Files:**
- Modify: `README.md` (add Day 5 execution example)
- Test: Full pytest suite & Ruff check

- [ ] **Step 1: Run full pytest suite across entire repository**

Run: `uv run pytest`
Expected: ALL tests pass (Day 1-4 tests + Day 5 runtime tests).

- [ ] **Step 2: Run Ruff lint and format checks**

Run: `uv run ruff check --fix .` and `uv run ruff format .`
Expected: Clean output with zero errors or warnings.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(readme): update README with Day 5 Agent Runtime usage"
```
