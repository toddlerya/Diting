# Diting MCP 服务层详细设计说明书 (Mock MCP Servers Specification)

## 1. 概述与设计原则

本项目底层仿真引擎通过轻量级 HTTP API (`State Server`) 暴露纯内存可观测性数据。为了向 Agent Runtime (如 LangGraph, AgentScope, AutoGen) 提供标准化的 Model Context Protocol (MCP) 接口，Diting 搭建一套标准 Mock MCP 服务层 (`mcp/`)。

### 设计原则
1. **职责隔离 (Separation of Concerns)**: 分别构建独立的 Prometheus, Loki, Trace, Knowledge MCP Server 进程，为 LangGraph 中的 Metrics, Logs, Trace, Knowledge Agent 提供严格的资源/工具作用域约束。
2. **官方 SDK 标准对齐**: 基于 Anthropic 官方 Python `mcp` SDK (`FastMCP`) 构建，完全兼容 MCP stdio 与 SSE/HTTP 传输协议。
3. **零外部重型依赖**: 不依赖真实的 Prometheus/Loki/Jaeger/FAISS 重型集群与向量数据库。可观测数据由 `state_client.py` 向仿真端 `State Server` 拉取，知识库采用 `rank-bm25` 纯内存 BM25 算法检索。

---

## 2. 模块结构与数据流架构

```text
mcp/
├── state_client.py          # State Server HTTP API 客户端 (含错误处理与 Fail-Fast)
├── prometheus_server.py     # Prometheus & Alertmanager MCP Server (Metrics & Alerts Tools)
├── loki_server.py           # Loki MCP Server (Logs Tools)
├── trace_server.py          # Trace MCP Server (Distributed Tracing Tools)
├── knowledge_server.py      # Knowledge MCP Server (BM25 降噪检索 Tools)
└── knowledge_base/          # Markdown 知识库目录
    ├── runbooks/            # 故障处置 SOP (redis_leak.md, oom.md)
    └── noise/               # 90% 混淆干预 Wiki (duty_roster.md, disk_mount.md 等 10+ 篇)
```

### 数据流结构图
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            LangGraph / LLM Agent                            │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ MCP Protocol (stdio / SSE)
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                  FastMCP Servers (Prometheus / Loki / Trace)                │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ StateClient (HTTP GET/DELETE)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                 Diting In-Memory State HTTP Server (Port 8000)              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                             Knowledge MCP Server                            │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ 本地内存加载与 BM25 检索
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                mcp/knowledge_base/ (Runbooks & 90% 噪声 Wiki)               │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 各 MCP Server 详细工具 (Tools) 规范与适配

### 3.1 State Client (`mcp/state_client.py`)
封装向 `http://127.0.0.1:8000` 发起的 HTTP 请求，统一处理网络异常与超时（`timeout=5.0s`）：
* `get_metrics(session_id, metric_name, start_tick, end_tick, real_now)`
* `get_logs(session_id, service, level, real_now)`
* `get_traces(session_id, real_now, trace_id=None)`：支持按 `trace_id` 向后端精准过滤或在客户端筛选。
* `get_alerts(session_id, status, real_now)`：获取 `firing` 或 `resolved` 告警。
* `delete_session(session_id)`：向后端发送 `DELETE /api/v1/session` 重置会话数据。
* **异常处理策略**: 捕捉 `httpx.HTTPError` 与 `httpx.TimeoutException`，抛出强类型 `StateClientError` 异常，由 FastMCP 工具包装返回友好的 JSON Error Response。

### 3.2 Prometheus MCP Server (`mcp/prometheus_server.py`)
* **`query_range(session_id: str, metric_name: str, start_tick: int = 0, end_tick: int = 100)`**
  * 查询特定指标在离线 tick 区间的时序曲线，返回包含实时 UTC (`+00:00`) 时间戳与数值的数据列表。
* **`query_instant(session_id: str, metric_name: str)`**
  * 瞬时查询最新 tick 的指标快照。
* **`list_metrics(session_id: str)`**
  * 列出当前 Session 已采集的指标名称集合（如 `gateway_cpu_usage`, `redis_utilization`）。
* **`query_alerts(session_id: str, status: str = "firing")`**
  * 补齐 Alertmanager 告警生命周期查询工具。返回激活中 (`firing`) 或已消解 (`resolved`) 的告警列表（包含 `startsAt`, `endsAt`, `labels`, `annotations`）。

### 3.3 Loki MCP Server (`mcp/loki_server.py`)
* **`query_logs(session_id: str, service: str, level: str = "ERROR")`**
  * 查询指定微服务在特定级别的日志流，返回带 ISO 对齐时间戳、`trace_id` 及错误上下文的格式化日志行。
* **`list_services(session_id: str)`**
  * 列出当前 Session 数据库中包含日志的服务清单。

### 3.4 Trace MCP Server (`mcp/trace_server.py`)
* **`get_trace(session_id: str, trace_id: str)`**
  * 根据 `trace_id` 向 `StateClient` 获取单次请求完整的分布式 Span 树骨架、各节点耗时与重试链路。同时在 `state_server.py` 的 `/api/v1/traces` 端点增加可选 `trace_id` 查询参数以提升检索性能。
* **`search_traces(session_id: str, min_duration_ms: float = 0.0)`**
  * 检索 Session 内耗时超过 `min_duration_ms` 的 Slow Trace 列表。

### 3.5 Knowledge MCP Server (`mcp/knowledge_server.py`)
* **`search_runbooks(session_id: str, query_term: str, top_k: int = 3)`**
  * 依赖 `rank-bm25` 库中的 `BM25Okapi` 算法对 `mcp/knowledge_base/` 目录下的所有 Markdown 文档执行相关度计算。
  * **文档库构成**: 2 篇核心故障处置 SOP (`redis_leak.md`, `oom.md`) + 10 篇无关运维噪声 Wiki (`duty_roster.md`, `disk_mount.md` 等)。
  * **分词与打分**: 使用正则与英文/中文标记分词预建 BM25 索引。
  * **返回值**: Top-K 最相关的文档（包含文档名、相关度得分、标题与正文摘要）。

---

## 4. 依赖配置与测试策略

### 4.1 依赖项 (`pyproject.toml`)
* `mcp >= 1.2.0`
* `httpx >= 0.28.1`
* `rank-bm25 >= 0.2.2`
* `respx >= 0.22.0` (开发测试依赖，用于 Mock HTTP 请求)

### 4.2 单元测试策略 (`tests/mcp/`)
1. **`tests/mcp/test_state_client.py`**:
   * 使用 `respx` 拦截与 Mock HTTP 响应，测试 `StateClient` 的各项 API 查询、`delete_session` 接口以及网络超时/断连时的 `StateClientError` 异常捕捉。
2. **`tests/mcp/test_mcp_servers.py`**:
   * 使用 FastMCP 工具函数的直接调用或 TestClient 验证 `query_range`, `query_logs`, `get_trace`, `query_alerts` 等工具的参数校验和返回值 Schema 结构。
3. **`tests/mcp/test_knowledge_bm25.py`**:
   * **Recall@K 召回率测试**: 在 10+ 篇噪声 Markdown 的干扰下，使用关键词（如 `"Redis connection leak"`、`"OutOfMemoryError"`）进行检索，断言 Ground Truth Runbook（如 `redis_leak.md`）必然排在 Top-1，测试降噪有效性。
