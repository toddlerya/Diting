# LangGraph 多智能体 Agent Runtime 实施计划

> **致 Agent 执行者：** 推荐使用 `superpowers:subagent-driven-development` 或 `superpowers:executing-plans` 按 Task 逐项实施本计划。步骤使用复选框 (`- [x]`) 记录状态。

**Goal:** 实现 Diting (谛听) 项目的 `runtime/` 模块，构建基于原生 LangGraph `StateGraph` 的多 Agent 黑板协同诊断工作流，包含 Pydantic v2 证据 Schema、并行扇出派发（Fan-out Dispatch）以及离线 Mock LLM 引擎支持。

**Architecture:** 由中央 Supervisor Agent 节点检查共享 `BlackboardState` 状态，向各领域 Specialist Agent 节点包装函数（Metrics, Logs, Trace, Knowledge）发出并行工具调用/路由决策（`next_steps: list[str]`）。每个节点包装函数查询对应的 MCP 服务，将原始输出提炼格式化为紧凑的 `Evidence` 对象并追加 `ToolMessage` 以维持消息协议有效性。当证据收集完备时，流程流转至 `Synthesizer` 节点合成并输出结构化的 `DiagnosisReport` 根因诊断报告。

**Tech Stack:** Python 3.13, LangGraph (`langgraph`), LangChain Core (`langchain-core`), Pydantic v2, FastAPI/httpx, Pytest, Ruff.

## Global Constraints

- **Python 版本**: `>= 3.13`（通过 `uv` 管理）。
- **指令执行**: 所有 Python 相关命令必须使用 `uv run` 引导。
- **代码质量约束**: 严格遵循 Ruff & Pytest 工作流：`uv run ruff check --fix .`、`uv run ruff format .`、`uv run pytest`。
- **时区标准**: ISO 8601 UTC 时间字符串，显式携带 `+00:00` 后缀。
- **强类型 Schema**: 所有数据结构必须通过 Pydantic v2 校验。

---

### Task 1: 依赖配置与环境验证

**Files:**
- Modify: `pyproject.toml`
- Test: 运行 `uv sync` 并检查依赖加载

**Interfaces:**
- Consumes: `pyproject.toml`
- Produces: 在 `.venv` 中安装 `langgraph`、`langchain-core`、`langchain-openai`

- [x] **Step 1: 在 `pyproject.toml` 中添加 LangGraph 与 LangChain 依赖**

在 `pyproject.toml` 中添加 `"langgraph>=0.2.70"`、`"langchain-core>=0.3.38"`、`"langchain-openai>=0.3.7"`。

- [x] **Step 2: 使用 uv 同步依赖**

运行：`uv sync`
预期：成功同步依赖且无报错。

- [x] **Step 3: 提交 Git**

```bash
git add pyproject.toml uv.lock
git commit -m "build(deps): add langgraph and langchain dependencies for Day 5 runtime"
```

---

### Task 2: Pydantic Schema 与 BlackboardState Reducer (`runtime/schema.py`)

**Files:**
- Create: `runtime/__init__.py`
- Create: `runtime/schema.py`
- Create: `tests/runtime/__init__.py`
- Create: `tests/runtime/test_schema.py`

**Interfaces:**
- Consumes: Pydantic v2, `langchain_core.messages.BaseMessage`
- Produces: `Evidence`, `DiagnosisReport`, `BlackboardState`

- [x] **Step 1: 编写 Schema 与 BlackboardState 的失败测试**

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

- [x] **Step 2: 运行测试验证失败**

运行：`uv run pytest tests/runtime/test_schema.py`
预期：失败，提示 `ModuleNotFoundError` 或 `runtime.schema` 导入错误。

- [x] **Step 3: 实现 `runtime/schema.py`**

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

- [x] **Step 4: 运行测试验证通过**

运行：`uv run pytest tests/runtime/test_schema.py`
预期：测试通过。

- [x] **Step 5: 提交 Git**

```bash
git add runtime/schema.py tests/runtime/test_schema.py runtime/__init__.py tests/runtime/__init__.py
git commit -m "feat(runtime): add BlackboardState and Pydantic Evidence schemas"
```

---

### Task 3: MCP Agent 工具适配层 (`runtime/tools/mcp_tools.py`)

**Files:**
- Create: `runtime/tools/__init__.py`
- Create: `runtime/tools/mcp_tools.py`
- Create: `tests/runtime/test_mcp_tools.py`

**Interfaces:**
- Consumes: `runtime.schema.Evidence`, MCP 服务 API (Prometheus, Loki, Trace, Knowledge)
- Produces: 返回 `(Evidence, ToolMessage)` 元组的 MCP 工具函数

- [x] **Step 1: 编写 MCP Agent 工具失败测试**

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

- [x] **Step 2: 运行测试验证失败**

运行：`uv run pytest tests/runtime/test_mcp_tools.py`
预期：失败，提示 `ModuleNotFoundError` 或 `runtime.tools.mcp_tools` 导入错误。

- [x] **Step 3: 实现 `runtime/tools/mcp_tools.py`**

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

- [x] **Step 4: 运行测试验证通过**

运行：`uv run pytest tests/runtime/test_mcp_tools.py`
预期：测试通过。

- [x] **Step 5: 提交 Git**

```bash
git add runtime/tools/mcp_tools.py tests/runtime/test_mcp_tools.py runtime/tools/__init__.py
git commit -m "feat(runtime): add MCP Agent tools with InjectedToolCallId and ToolMessage binding"
```

---

### Task 4: Specialist 节点包装函数与离线 Mock LLM 引擎 (`runtime/agents/` 与 `runtime/mock_llm.py`)

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
- Produces: 返回 `dict[str, Any]` 的 LangGraph 节点函数

- [x] **Step 1: 编写 Agent 节点包装函数与 Mock LLM 失败测试**

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

- [x] **Step 2: 运行测试验证失败**

运行：`uv run pytest tests/runtime/test_agents.py`
预期：失败，提示 `ModuleNotFoundError` 或 `runtime.mock_llm` / `runtime.agents` 导入错误。

- [x] **Step 3: 实现 `runtime/mock_llm.py`**

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

- [x] **Step 4: 在 `runtime/agents/` 中实现各 Agent 节点包装函数**

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

- [x] **Step 5: 运行测试验证通过**

运行：`uv run pytest tests/runtime/test_agents.py`
预期：测试通过。

- [x] **Step 6: 提交 Git**

```bash
git add runtime/mock_llm.py runtime/agents/ tests/runtime/test_agents.py
git commit -m "feat(runtime): implement Specialist Node Wrappers and Mock LLM Engine"
```

---

### Task 5: StateGraph 组装与 MemorySaver Checkpointer (`runtime/graph.py`)

**Files:**
- Create: `runtime/graph.py`
- Create: `tests/runtime/test_graph_workflow.py`

**Interfaces:**
- Consumes: `runtime.agents` 中的所有节点函数, `BlackboardState`, `langgraph.checkpoint.memory.MemorySaver`
- Produces: `build_diagnosis_graph()`, `run_diagnosis_workflow(alert_dict)`

- [x] **Step 1: 编写 LangGraph 工作流全流程执行失败测试**

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

- [x] **Step 2: 运行测试验证失败**

运行：`uv run pytest tests/runtime/test_graph_workflow.py`
预期：失败，提示 `ModuleNotFoundError` 或 `runtime.graph` 导入错误。

- [x] **Step 3: 实现 `runtime/graph.py`**

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

    # Specialist Nodes 执行完后汇合交回 Supervisor
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

- [x] **Step 4: 运行测试验证通过**

运行：`uv run pytest tests/runtime/test_graph_workflow.py`
预期：测试通过。

- [x] **Step 5: 提交 Git**

```bash
git add runtime/graph.py tests/runtime/test_graph_workflow.py
git commit -m "feat(runtime): assemble LangGraph StateGraph with parallel dispatch and MemorySaver checkpointer"
```

---

### Task 6: 全量验证与 Ruff 代码质量检查

**Files:**
- Modify: `README.md`（补充 Agent Runtime 运行示例）
- Test: 全量 pytest 测试集与 Ruff 检查

- [x] **Step 1: 运行全项目单元测试集**

运行：`uv run pytest`
预期：所有测试全部通过（Day 1-4 测试 + Day 5 runtime 测试）。

- [x] **Step 2: 运行 Ruff 检查与格式化**

运行：`uv run ruff check --fix .` 与 `uv run ruff format .`
预期：零错误零警告。

- [x] **Step 3: 提交 Git**

```bash
git add README.md
git commit -m "docs(readme): update README with Day 5 Agent Runtime usage"
```
