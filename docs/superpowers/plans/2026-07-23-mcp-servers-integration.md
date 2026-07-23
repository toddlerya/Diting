# Diting MCP Server Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Diting 仿真平台构建标准的 Mock MCP 服务层（包含 Prometheus、Loki、Trace 与基于 BM25 降噪检索的 Knowledge MCP Server）。

**Architecture:** 采用 Anthropic 官方 Python `mcp.server.fastmcp.FastMCP` 分别实现 4 个职责隔离的 MCP Server 进程；通过底层 `state_client.py` 向仿真端 `State Server` (`http://127.0.0.1:8000`) 拉取内存数据；Knowledge Server 采用 `rank-bm25` 纯内存检索算法在混杂 90% 干扰 Wiki 的知识库中进行精准 Ground Truth 匹配。

**Tech Stack:** Python 3.13, `mcp>=1.2.0`, `rank-bm25>=0.2.2`, `httpx>=0.28.1`, `fastapi>=0.139.2`, `pytest>=9.1.1`

## Global Constraints

* 包管理器统一使用 `uv`，国内镜像源 `https://mirrors.aliyun.com/pypi/simple/`。
* `pyproject.toml` 中需配置 `pythonpath = ["."]` 确保 `uv run pytest` 开箱即用。
* 所有时间戳输出必须显式对齐为 ISO 8601 带 `+00:00` 后缀（UTC 标准时间）。
* 遵循 TDD 规范：编写失败测试 -> 验证失败 -> 编写最小实现 -> 验证通过 -> git commit。

---

### Task 1: Environment Dependencies & Pytest Configuration

**Files:**
- Modify: `pyproject.toml:1-15`
- Test: Run `uv run pytest -v`

**Interfaces:**
- Consumes: None
- Produces: `pyproject.toml` with `mcp`, `rank-bm25` dependencies and `[tool.pytest.ini_options]` config.

- [ ] **Step 1: 更新 `pyproject.toml`**

  修改 `pyproject.toml` 内容：
  ```toml
  [project]
  name = "diting"
  version = "0.1.0"
  description = "Agent ASSEP Simulation & Evaluation Platform"
  readme = "README.md"
  requires-python = ">=3.13"
  dependencies = [
      "fastapi>=0.139.2",
      "httpx>=0.28.1",
      "mcp>=1.2.0",
      "pydantic>=2.13.4",
      "pytest>=9.1.1",
      "pyyaml>=6.0.1",
      "rank-bm25>=0.2.2",
      "uvicorn>=0.51.0",
  ]

  [tool.pytest.ini_options]
  pythonpath = ["."]
  ```

- [ ] **Step 2: 同步虚拟环境依赖**

  Run: `uv sync --index-url https://mirrors.aliyun.com/pypi/simple/`
  Expected: Success

- [ ] **Step 3: 运行全量测试验证 `pythonpath` 生效**

  Run: `uv run pytest -v`
  Expected: PASS (23 passed, no ModuleNotFoundError)

- [ ] **Step 4: Commit**

  ```bash
  git add pyproject.toml uv.lock
  git commit -m "chore(env): add mcp and rank-bm25 dependencies with pytest pythonpath"
  ```

---

### Task 2: State Server HTTP Client with Fail-Fast Error Handling

**Files:**
- Create: `mcp/state_client.py`
- Test: `tests/mcp/test_state_client.py`

**Interfaces:**
- Consumes: `http://127.0.0.1:8000/api/v1/...`
- Produces:
  * `StateClient(base_url: str = "http://127.0.0.1:8000", timeout: float = 5.0)`
  * `get_metrics(session_id: str, metric_name: str, start_tick: int, end_tick: int, real_now: str | None = None) -> list[dict]`
  * `get_logs(session_id: str, service: str, level: str, real_now: str | None = None) -> list[str]`
  * `get_traces(session_id: str, real_now: str | None = None) -> list[dict]`
  * `get_alerts(session_id: str, status: str = "firing", real_now: str | None = None) -> list[dict]`
  * `delete_session(session_id: str) -> dict`

- [ ] **Step 1: 编写失败的测试**

  创建 `tests/mcp/test_state_client.py`：
  ```python
  import pytest
  import httpx
  from mcp.state_client import StateClient

  def test_state_client_success():
      # 使用 MockTransport 模拟 HTTP 成功响应
      def handler(request: httpx.Request):
          if request.url.path == "/api/v1/metrics":
              return httpx.Response(200, json=[{"timestamp": "2026-07-23T00:00:00+00:00", "value": 42.0}])
          elif request.url.path == "/api/v1/session":
              return httpx.Response(200, json={"status": "cleared", "session_id": "s1"})
          return httpx.Response(404)

      transport = httpx.MockTransport(handler)
      client = StateClient(transport=transport)
      res = client.get_metrics("s1", "cpu_usage", 0, 10)
      assert len(res) == 1
      assert res[0]["value"] == 42.0

      del_res = client.delete_session("s1")
      assert del_res["status"] == "cleared"

  def test_state_client_unreachable_fail_fast():
      # 模拟无法连接 Server
      def handler(request: httpx.Request):
          raise httpx.ConnectError("Connection refused")

      transport = httpx.MockTransport(handler)
      client = StateClient(transport=transport)
      with pytest.raises(RuntimeError, match="State Server not reachable"):
          client.get_metrics("s1", "cpu_usage", 0, 10)
  ```

- [ ] **Step 2: 运行测试验证失败**

  Run: `uv run pytest tests/mcp/test_state_client.py -v`
  Expected: FAIL (ImportError: No module named 'mcp.state_client')

- [ ] **Step 3: 编写 StateClient 最小实现**

  创建 `mcp/state_client.py`：
  ```python
  from typing import Any, Dict, List, Optional
  import httpx


  class StateClient:
      """
      Diting In-Memory State HTTP Server 客户端。
      具备超时拦截与 Fail-Fast 友好异常捕获。
      """
      def __init__(self, base_url: str = "http://127.0.0.1:8000", timeout: float = 5.0, transport: Optional[httpx.BaseTransport] = None):
          self.base_url = base_url.rstrip("/")
          self.timeout = timeout
          self.transport = transport

      def _get_client(self) -> httpx.Client:
          return httpx.Client(base_url=self.base_url, timeout=self.timeout, transport=self.transport)

      def _request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
          try:
              with self._get_client() as client:
                  resp = client.request(method, path, params=params)
                  resp.raise_for_status()
                  return resp.json()
          except (httpx.ConnectError, httpx.ConnectTimeout) as e:
              raise RuntimeError(f"Diting State Server not reachable at {self.base_url}. Please start state server first.") from e
          except httpx.HTTPStatusError as e:
              raise RuntimeError(f"State Server API Error: {e.response.status_code} - {e.response.text}") from e

      def get_metrics(self, session_id: str, metric: str, start_tick: int = 0, end_tick: int = 100, real_now: Optional[str] = None) -> List[Dict[str, Any]]:
          params = {"session_id": session_id, "metric": metric, "start_tick": start_tick, "end_tick": end_tick}
          if real_now:
              params["real_now"] = real_now
          return self._request("GET", "/api/v1/metrics", params=params)

      def get_logs(self, session_id: str, service: str, level: str = "ERROR", real_now: Optional[str] = None) -> List[str]:
          params = {"session_id": session_id, "service": service, "level": level}
          if real_now:
              params["real_now"] = real_now
          return self._request("GET", "/api/v1/logs", params=params)

      def get_traces(self, session_id: str, real_now: Optional[str] = None) -> List[Dict[str, Any]]:
          params = {"session_id": session_id}
          if real_now:
              params["real_now"] = real_now
          return self._request("GET", "/api/v1/traces", params=params)

      def get_alerts(self, session_id: str, status: str = "firing", real_now: Optional[str] = None) -> List[Dict[str, Any]]:
          params = {"session_id": session_id, "status": status}
          if real_now:
              params["real_now"] = real_now
          return self._request("GET", "/api/v1/alerts", params=params)

      def delete_session(self, session_id: str) -> Dict[str, Any]:
          return self._request("DELETE", "/api/v1/session", params={"session_id": session_id})
  ```

- [ ] **Step 4: 运行测试验证通过**

  Run: `uv run pytest tests/mcp/test_state_client.py -v`
  Expected: PASS

- [ ] **Step 5: Commit**

  ```bash
  git add mcp/state_client.py tests/mcp/test_state_client.py
  git commit -m "feat(mcp): implement StateClient HTTP client with Fail-Fast error handling"
  ```

---

### Task 3: Knowledge MCP Server & BM25 Noise Reduction Engine

**Files:**
- Create: `mcp/knowledge_base/runbooks/redis_pool_leak.md`
- Create: `mcp/knowledge_base/runbooks/service_oom.md`
- Create: 10+ Markdown files under `mcp/knowledge_base/noise/`
- Create: `mcp/knowledge_server.py`
- Test: `tests/mcp/test_knowledge_server.py`

**Interfaces:**
- Consumes: Local Markdown files in `mcp/knowledge_base/`
- Produces: `mcp/knowledge_server.py` FastMCP server with tool `search_runbooks(session_id: str, query_term: str, top_k: int = 3) -> list[dict]`

- [ ] **Step 1: 创建知识库基准数据 (Runbooks & Noise Wikis)**

  在 `mcp/knowledge_base/runbooks/redis_pool_leak.md` 中写入真实故障 Runbook：
  ```markdown
  # Redis Connection Pool Leak Runbook
  ## Description
  PaymentService or OrderService fails to acquire Redis connection due to pool connection leak.
  ## Symptoms
  - Log: `Failed to acquire Redis connection (50/50 active)`
  - Metric: `redis_active_connections` hits limit.
  ## Resolution
  Restart PaymentService and scale up Redis pool capacity.
  ```

  在 `mcp/knowledge_base/runbooks/service_oom.md` 中写入 OOM Runbook：
  ```markdown
  # Service Out Of Memory (OOM) Runbook
  ## Description
  Service crashes due to java.lang.OutOfMemoryError.
  ## Resolution
  Analyze heap dump, increase max_heap_mb, restart service.
  ```

  在 `mcp/knowledge_base/noise/` 目录下放置 10 篇干预杂噪 Wiki：
  - `duty_roster.md` (运维值班表)
  - `disk_mount_guide.md` (虚拟机磁盘挂载手册)
  - `mysql_backup.md` (数据库备份常规操作)
  - `network_vpn.md` (VPN 连接指引)
  - `k8s_ingress_config.md` (Ingress 语法指南)
  - `grafana_dashboard_setup.md` (仪表盘配置说明)
  - `bastion_host_access.md` (跳板机申请规则)
  - `gitlab_ci_pipeline.md` (CI 流水线配置)
  - `kafka_topic_cleanup.md` (Kafka Topic 清理规则)
  - `redis_cluster_migration.md` (Redis 集群平滑迁移指南)

- [ ] **Step 2: 编写失败的测试**

  创建 `tests/mcp/test_knowledge_server.py`：
  ```python
  import pytest
  from mcp.knowledge_server import search_runbooks_engine

  def test_bm25_search_recall_under_noise():
      # 验证输入 Redis 泄漏关键词时，算法能够打败 10+ 篇干扰文档，将精确 Runbook 检索至 Top-1
      results = search_runbooks_engine("Redis connection pool leak", top_k=3)
      assert len(results) > 0
      assert results[0]["filename"] == "redis_pool_leak.md"
      assert results[0]["score"] > 0
  ```

- [ ] **Step 3: 运行测试验证失败**

  Run: `uv run pytest tests/mcp/test_knowledge_server.py -v`
  Expected: FAIL (ImportError)

- [ ] **Step 4: 编写 Knowledge Server 与 BM25 检索引擎**

  创建 `mcp/knowledge_server.py`：
  ```python
  from pathlib import Path
  from typing import Any, Dict, List
  from rank_bm25 import BM25Okapi
  from mcp.server.fastmcp import FastMCP

  mcp = FastMCP("Knowledge MCP Server")

  KNOWLEDGE_BASE_DIR = Path(__file__).resolve().parent / "knowledge_base"


  def _load_documents() -> List[Dict[str, Any]]:
      docs = []
      if not KNOWLEDGE_BASE_DIR.exists():
          return docs

      for filepath in KNOWLEDGE_BASE_DIR.glob("**/*.md"):
          content = filepath.read_text(encoding="utf-8")
          lines = content.strip().splitlines()
          title = lines[0].lstrip("# ").strip() if lines else filepath.name
          docs.append({
              "filename": filepath.name,
              "path": str(filepath),
              "title": title,
              "content": content,
              "tokens": content.lower().split()
          })
      return docs


  def search_runbooks_engine(query_term: str, top_k: int = 3) -> List[Dict[str, Any]]:
      docs = _load_documents()
      if not docs:
          return []

      corpus = [doc["tokens"] for doc in docs]
      bm25 = BM25Okapi(corpus)

      query_tokens = query_term.lower().split()
      scores = bm25.get_scores(query_tokens)

      scored_docs = []
      for idx, score in enumerate(scores):
          if score > 0:
              d = docs[idx]
              scored_docs.append({
                  "filename": d["filename"],
                  "title": d["title"],
                  "score": float(score),
                  "snippet": d["content"][:300]
              })

      scored_docs.sort(key=lambda x: x["score"], reverse=True)
      return scored_docs[:top_k]


  @mcp.tool()
  def search_runbooks(session_id: str, query_term: str, top_k: int = 3) -> List[Dict[str, Any]]:
      """
      Search operational runbooks and troubleshooting guides using BM25 text relevance.
      """
      return search_runbooks_engine(query_term, top_k=top_k)


  if __name__ == "__main__":
      mcp.run()
  ```

- [ ] **Step 5: 运行测试验证通过**

  Run: `uv run pytest tests/mcp/test_knowledge_server.py -v`
  Expected: PASS

- [ ] **Step 6: Commit**

  ```bash
  git add mcp/knowledge_base/ mcp/knowledge_server.py tests/mcp/test_knowledge_server.py
  git commit -m "feat(mcp): implement Knowledge MCP Server with rank-bm25 noise reduction"
  ```

---

### Task 4: Prometheus MCP Server (Metrics & Alerts Tools)

**Files:**
- Create: `mcp/prometheus_server.py`
- Test: `tests/mcp/test_prometheus_server.py`

**Interfaces:**
- Consumes: `StateClient`
- Produces: `FastMCP` Prometheus server with tools:
  * `query_range(session_id: str, metric_name: str, start_tick: int = 0, end_tick: int = 100) -> list[dict]`
  * `query_instant(session_id: str, metric_name: str) -> dict`
  * `list_metrics(session_id: str) -> list[str]`
  * `get_alerts(session_id: str, status: str = "firing") -> list[dict]`

- [ ] **Step 1: 编写失败的测试**

  创建 `tests/mcp/test_prometheus_server.py`：
  ```python
  import pytest
  import httpx
  from mcp.state_client import StateClient
  from mcp.prometheus_server import query_range_tool, query_instant_tool, get_alerts_tool

  def test_prometheus_mcp_tools():
      def handler(request: httpx.Request):
          if request.url.path == "/api/v1/metrics":
              return httpx.Response(200, json=[
                  {"timestamp": "2026-07-23T00:00:00+00:00", "value": 10.0},
                  {"timestamp": "2026-07-23T00:00:01+00:00", "value": 85.0}
              ])
          elif request.url.path == "/api/v1/alerts":
              return httpx.Response(200, json=[{"status": "firing", "labels": {"alertname": "HighLatency"}}])
          return httpx.Response(404)

      client = StateClient(transport=httpx.MockTransport(handler))
      range_res = query_range_tool("s1", "gateway_cpu_usage", client=client)
      assert len(range_res) == 2

      instant_res = query_instant_tool("s1", "gateway_cpu_usage", client=client)
      assert instant_res["value"] == 85.0

      alerts_res = get_alerts_tool("s1", "firing", client=client)
      assert len(alerts_res) == 1
      assert alerts_res[0]["labels"]["alertname"] == "HighLatency"
  ```

- [ ] **Step 2: 运行测试验证失败**

  Run: `uv run pytest tests/mcp/test_prometheus_server.py -v`
  Expected: FAIL (ImportError)

- [ ] **Step 3: 编写 Prometheus MCP Server 实现**

  创建 `mcp/prometheus_server.py`：
  ```python
  from typing import Any, Dict, List, Optional
  from mcp.server.fastmcp import FastMCP
  from mcp.state_client import StateClient

  mcp = FastMCP("Prometheus MCP Server")
  _default_client = StateClient()


  def query_range_tool(session_id: str, metric_name: str, start_tick: int = 0, end_tick: int = 100, client: Optional[StateClient] = None) -> List[Dict[str, Any]]:
      c = client or _default_client
      return c.get_metrics(session_id, metric_name, start_tick, end_tick)


  def query_instant_tool(session_id: str, metric_name: str, client: Optional[StateClient] = None) -> Dict[str, Any]:
      c = client or _default_client
      pts = c.get_metrics(session_id, metric_name, start_tick=0, end_tick=999999)
      if pts:
          return pts[-1]
      return {"timestamp": None, "value": None}


  def list_metrics_tool(session_id: str, client: Optional[StateClient] = None) -> List[str]:
      c = client or _default_client
      pts = c.get_metrics(session_id, "*", start_tick=0, end_tick=999999)
      return list({p.get("metric_name", "") for p in pts if "metric_name" in p})


  def get_alerts_tool(session_id: str, status: str = "firing", client: Optional[StateClient] = None) -> List[Dict[str, Any]]:
      c = client or _default_client
      return c.get_alerts(session_id, status=status)


  @mcp.tool()
  def query_range(session_id: str, metric_name: str, start_tick: int = 0, end_tick: int = 100) -> List[Dict[str, Any]]:
      """Query Prometheus range time-series metrics."""
      return query_range_tool(session_id, metric_name, start_tick, end_tick)


  @mcp.tool()
  def query_instant(session_id: str, metric_name: str) -> Dict[str, Any]:
      """Query Prometheus instant metric value snapshot."""
      return query_instant_tool(session_id, metric_name)


  @mcp.tool()
  def list_metrics(session_id: str) -> List[str]:
      """List available metric names recorded for current session."""
      return list_metrics_tool(session_id)


  @mcp.tool()
  def get_alerts(session_id: str, status: str = "firing") -> List[Dict[str, Any]]:
      """Query Alertmanager active firing or resolved alerts for the session."""
      return get_alerts_tool(session_id, status)


  if __name__ == "__main__":
      mcp.run()
  ```

- [ ] **Step 4: 运行测试验证通过**

  Run: `uv run pytest tests/mcp/test_prometheus_server.py -v`
  Expected: PASS

- [ ] **Step 5: Commit**

  ```bash
  git add mcp/prometheus_server.py tests/mcp/test_prometheus_server.py
  git commit -m "feat(mcp): implement Prometheus MCP Server with query_range and get_alerts"
  ```

---

### Task 5: Loki MCP Server (Logs Tools)

**Files:**
- Create: `mcp/loki_server.py`
- Test: `tests/mcp/test_loki_server.py`

**Interfaces:**
- Consumes: `StateClient`
- Produces: `FastMCP` Loki server with tools:
  * `query_logs(session_id: str, service: str, level: str = "ERROR") -> list[str]`
  * `list_services(session_id: str) -> list[str]`

- [ ] **Step 1: 编写失败的测试**

  创建 `tests/mcp/test_loki_server.py`：
  ```python
  import pytest
  import httpx
  from mcp.state_client import StateClient
  from mcp.loki_server import query_logs_tool

  def test_loki_mcp_query_logs():
      def handler(request: httpx.Request):
          if request.url.path == "/api/v1/logs":
              return httpx.Response(200, json=[
                  "[2026-07-23T00:00:00+00:00] [ERROR] [trace_id: tr_123] PaymentService: Failed due to Redis timeout"
              ])
          return httpx.Response(404)

      client = StateClient(transport=httpx.MockTransport(handler))
      logs = query_logs_tool("s1", "PaymentService", "ERROR", client=client)
      assert len(logs) == 1
      assert "Redis timeout" in logs[0]
  ```

- [ ] **Step 2: 运行测试验证失败**

  Run: `uv run pytest tests/mcp/test_loki_server.py -v`
  Expected: FAIL (ImportError)

- [ ] **Step 3: 编写 Loki MCP Server 实现**

  创建 `mcp/loki_server.py`：
  ```python
  from typing import List, Optional
  from mcp.server.fastmcp import FastMCP
  from mcp.state_client import StateClient

  mcp = FastMCP("Loki MCP Server")
  _default_client = StateClient()


  def query_logs_tool(session_id: str, service: str, level: str = "ERROR", client: Optional[StateClient] = None) -> List[str]:
      c = client or _default_client
      return c.get_logs(session_id, service, level)


  def list_services_tool(session_id: str, client: Optional[StateClient] = None) -> List[str]:
      c = client or _default_client
      logs = c.get_logs(session_id, service="*", level="*")
      services = set()
      for log in logs:
          parts = log.split(" ")
          if len(parts) >= 4:
              services.add(parts[3].rstrip(":"))
      return list(services)


  @mcp.tool()
  def query_logs(session_id: str, service: str, level: str = "ERROR") -> List[str]:
      """Query Loki logs for a specific service and severity level."""
      return query_logs_tool(session_id, service, level)


  @mcp.tool()
  def list_services(session_id: str) -> List[str]:
      """List services that have recorded logs in the session."""
      return list_services_tool(session_id)


  if __name__ == "__main__":
      mcp.run()
  ```

- [ ] **Step 4: 运行测试验证通过**

  Run: `uv run pytest tests/mcp/test_loki_server.py -v`
  Expected: PASS

- [ ] **Step 5: Commit**

  ```bash
  git add mcp/loki_server.py tests/mcp/test_loki_server.py
  git commit -m "feat(mcp): implement Loki MCP Server for querying logs"
  ```

---

### Task 6: Trace MCP Server (Distributed Tracing Tools)

**Files:**
- Create: `mcp/trace_server.py`
- Test: `tests/mcp/test_trace_server.py`

**Interfaces:**
- Consumes: `StateClient`
- Produces: `FastMCP` Trace server with tools:
  * `get_trace(session_id: str, trace_id: str) -> dict | None`
  * `search_traces(session_id: str, min_duration_ms: float = 0.0) -> list[dict]`

- [ ] **Step 1: 编写失败的测试**

  创建 `tests/mcp/test_trace_server.py`：
  ```python
  import pytest
  import httpx
  from mcp.state_client import StateClient
  from mcp.trace_server import get_trace_tool, search_traces_tool

  def test_trace_mcp_tools():
      mock_traces = [
          {
              "trace_id": "tr_001",
              "timestamp": "2026-07-23T00:00:00+00:00",
              "request": {"root_span": {"service": "Gateway", "duration": 600.0, "status": "TIMEOUT"}}
          },
          {
              "trace_id": "tr_002",
              "timestamp": "2026-07-23T00:00:01+00:00",
              "request": {"root_span": {"service": "Gateway", "duration": 10.0, "status": "OK"}}
          }
      ]

      def handler(request: httpx.Request):
          if request.url.path == "/api/v1/traces":
              return httpx.Response(200, json=mock_traces)
          return httpx.Response(404)

      client = StateClient(transport=httpx.MockTransport(handler))

      # 验证按 trace_id 精确过滤
      tr = get_trace_tool("s1", "tr_001", client=client)
      assert tr is not None
      assert tr["trace_id"] == "tr_001"

      # 验证按 duration 过滤 slow traces
      slow = search_traces_tool("s1", min_duration_ms=500.0, client=client)
      assert len(slow) == 1
      assert slow[0]["trace_id"] == "tr_001"
  ```

- [ ] **Step 2: 运行测试验证失败**

  Run: `uv run pytest tests/mcp/test_trace_server.py -v`
  Expected: FAIL (ImportError)

- [ ] **Step 3: 编写 Trace MCP Server 实现**

  创建 `mcp/trace_server.py`：
  ```python
  from typing import Any, Dict, List, Optional
  from mcp.server.fastmcp import FastMCP
  from mcp.state_client import StateClient

  mcp = FastMCP("Trace MCP Server")
  _default_client = StateClient()


  def get_trace_tool(session_id: str, trace_id: str, client: Optional[StateClient] = None) -> Optional[Dict[str, Any]]:
      c = client or _default_client
      traces = c.get_traces(session_id)
      for tr in traces:
          if tr.get("trace_id") == trace_id:
              return tr
      return None


  def search_traces_tool(session_id: str, min_duration_ms: float = 0.0, client: Optional[StateClient] = None) -> List[Dict[str, Any]]:
      c = client or _default_client
      traces = c.get_traces(session_id)
      results = []
      for tr in traces:
          root_span = tr.get("request", {}).get("root_span", {})
          duration = root_span.get("duration", 0.0)
          if duration >= min_duration_ms:
              results.append(tr)
      return results


  @mcp.tool()
  def get_trace(session_id: str, trace_id: str) -> Optional[Dict[str, Any]]:
      """Get detailed trace span tree by trace_id."""
      return get_trace_tool(session_id, trace_id)


  @mcp.tool()
  def search_traces(session_id: str, min_duration_ms: float = 0.0) -> List[Dict[str, Any]]:
      """Search slow traces exceeding min_duration_ms threshold."""
      return search_traces_tool(session_id, min_duration_ms)


  if __name__ == "__main__":
      mcp.run()
  ```

- [ ] **Step 4: 运行测试验证通过**

  Run: `uv run pytest tests/mcp/test_trace_server.py -v`
  Expected: PASS

- [ ] **Step 5: Commit**

  ```bash
  git add mcp/trace_server.py tests/mcp/test_trace_server.py
  git commit -m "feat(mcp): implement Trace MCP Server for distributed trace inspection"
  ```

---

### Task 7: Full Test Suite Verification

**Files:**
- Test: All tests under `tests/`

- [ ] **Step 1: 运行 ruff 自动修饰与 Lint 校验**

  Run: `uv run ruff check --fix .`
  Expected: Clean, no lint errors

- [ ] **Step 2: 运行 ruff 格式化校验**

  Run: `uv run ruff format .`
  Expected: Code formatted

- [ ] **Step 3: 运行全量 Pytest 单元测试**

  Run: `uv run pytest -v`
  Expected: PASS (All tests pass)
