# Diting MCP 服务层详细设计说明书 (Mock MCP Servers Specification)

## 1. 概述与设计原则

本项目底层仿真引擎通过轻量级 HTTP API (`State Server`) 暴露纯内存可观测性数据。为了向 Agent Runtime (如 LangGraph, AgentScope, AutoGen) 提供标准化的 Model Context Protocol (MCP) 接口，Diting 搭建一套标准 Mock MCP 服务层 (`mcp/`)。

### 设计原则
1. **职责隔离 (Separation of Concerns)**: 分别构建独立的 Prometheus, Loki, Trace, Knowledge MCP Server 进程，为 LangGraph 中的 Metrics, Logs, Trace, Knowledge Agent 提供严格的资源/工具作用域约束。
2. **官方 SDK 标准对齐**: 基于 Anthropic 官方 Python `mcp` SDK (`FastMCP`) 构建，完全兼容 MCP stdio 与 SSE/HTTP 传输协议。
3. **零外部重型依赖**: 不依赖真实的 Prometheus/Loki/Jaeger/FAISS 重型集群与向量数据库。数据由 `state_client.py` 向仿真端 `State Server` 拉取，知识库采用纯内存 **BM25** 排序检索。

---

## 2. 模块结构与数据流架构

```text
mcp/
├── state_client.py          # State Server HTTP API 客户端
├── prometheus_server.py     # Prometheus MCP Server (Metrics Tools)
├── loki_server.py           # Loki MCP Server (Logs Tools)
├── trace_server.py          # Trace MCP Server (Distributed Tracing Tools)
├── knowledge_server.py      # Knowledge MCP Server (BM25 降噪检索 Tools)
└── knowledge_base/          # Markdown 知识库目录
    ├── runbooks/            # 故障处置 SOP (redis_leak.md, oom.md)
    └── noise/               # 90% 混淆干预 Wiki (duty_roster.md, disk_mount.md 等)
```

```
┌─────────────────────────────────────────────────────────────┐
│                  LangGraph / LLM Agent                      │
└──────────────────────────────┬──────────────────────────────┘
                               │ MCP Protocol (stdio / SSE)
┌──────────────────────────────▼──────────────────────────────┐
│           FastMCP Servers (Prometheus / Loki / Trace / Wiki) │
└──────────────────────────────┬──────────────────────────────┘
                               │ StateClient (HTTP)
┌──────────────────────────────▼──────────────────────────────┐
│        Diting In-Memory State HTTP Server (Port 8000)       │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 各 MCP Server 详细工具 (Tools) 规范

### 3.1 State Client (`mcp/state_client.py`)
封装向 `http://127.0.0.1:8000` 发起的 HTTP 请求：
* `get_metrics(session_id, metric_name, start_tick, end_tick, real_now)`
* `get_logs(session_id, service, level, real_now)`
* `get_traces(session_id, real_now)`
* `get_alerts(session_id, status, real_now)`

### 3.2 Prometheus MCP Server (`mcp/prometheus_server.py`)
* **`query_range(session_id: str, metric_name: str, start_tick: int = 0, end_tick: int = 100)`**
  * 查询特定指标在离线 tick 区间的时序曲线，返回包含实时 UTC (`+00:00`) 时间戳与数值的数据列表。
* **`query_instant(session_id: str, metric_name: str)`**
  * 瞬时查询最新 tick 的指标快照。
* **`list_metrics(session_id: str)`**
  * 列出当前 Session 已采集的指标名称集合（如 `gateway_cpu_usage`, `redis_utilization`）。

### 3.3 Loki MCP Server (`mcp/loki_server.py`)
* **`query_logs(session_id: str, service: str, level: str = "ERROR")`**
  * 查询指定微服务在特定级别的日志流，返回带 ISO 对齐时间戳、`trace_id` 及错误上下文的格式化日志行。
* **`list_services(session_id: str)`**
  * 列出当前 Session 数据库中包含日志的服务清单。

### 3.4 Trace MCP Server (`mcp/trace_server.py`)
* **`get_trace(session_id: str, trace_id: str)`**
  * 根据 `trace_id` 获取单次请求完整的分布式 Span 树骨架、各节点耗时与重试链路。
* **`search_traces(session_id: str, min_duration_ms: float = 0.0)`**
  * 检索 Session 内耗时超过 `min_duration_ms` 的 Slow Trace 列表。

### 3.5 Knowledge MCP Server (`mcp/knowledge_server.py`)
* **`search_runbooks(session_id: str, query_term: str, top_k: int = 3)`**
  * 对 `mcp/knowledge_base/` 目录下的所有 Markdown 文档执行 BM25 文本相关度计算。
  * **BM25 计算参数**: $k_1 = 1.5, b = 0.75$。
  * **返回值**: Top-K 最相关的文档（包含文档名、相关度得分、标题与正文摘要）。

---

## 4. 依赖更新与测试计划

1. **依赖升级**: 在 `pyproject.toml` 中添加 `mcp` 依赖。
2. **测试用例**: 在 `tests/mcp/` 目录下编写全面的测试单元，测试 HTTP State Client、各 FastMCP 工具函数的输入输出规范，以及 BM25 在强噪声打扰下的召回率与准确性。
