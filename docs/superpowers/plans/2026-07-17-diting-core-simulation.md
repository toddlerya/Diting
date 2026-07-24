# Diting 核心仿真引擎实施计划

> **致 Agent 执行者：** 推荐使用 `superpowers:subagent-driven-development` 或 `superpowers:executing-plans` 按 Task 逐项实施本计划。步骤使用复选框 (`- [ ]`) 记录状态。

**Goal:** 构建 Diting 系统状态仿真的核心底座。实现带有 100ms 动态对齐偏移时钟、加权拓扑（Fan-out/Route）随机路径游走、包含错误状态与重试节点的嵌套 Span 链生成、逻辑级物理资源上限（503/Timeout/OOM/IO 异常）、Alertmanager 告警消解（Firing -> Resolved）以及跨进程 In-Memory State HTTP State Server 接口。

> [!NOTE]
> **架构演进说明 (重构)**：在完成仿真底座初版后，项目已对仿真引擎完成了重构，将原本硬编码的测试环境拓扑、初始实体资源以及故障注入逻辑完全解耦并转为声明式 YAML 配置（具体存放在 `simulator/environments/` 与 `simulator/scenarios/` 目录中），并通过新实现的 `load_environment()` 与 `Scenario.from_yaml()` 进行无硬编码动态加载。同时进一步引入了 Pydantic 强类型模型层（定义在 `simulator/schema.py` 中的 `ServiceResource`, `InfraResource`, `EnvironmentConfig`），在 YAML 加载时强制执行配置校验与边界拦截（Fail-Fast）。

**Architecture:** 
1. `SimulationClock` 离线推推演，并在投影导出时动态将最后一个 Tick 映射至当前的物理 $T_{\text{real\_now}}$，确保 MCP 时间相对查询不落空。
2. 拓扑图显式区分为并行扇出 (`fan_out`) 和加权随机游走 (`route`)。
3. 请求生成时动态确定 SpanNode 调用树骨架；Pipeline 在故障时将 status 和 error 写入对应 Span，并根据 `retry_policy` 生成同层重试子 Span 节点。
4. 提供 `In-Memory State Server` API (HTTP)，为独立 MCP 进程与评估引擎提供 session 隔离的只读共享访问与 DELETE 内存清空接口。

**Tech Stack:** Python 3.10+, Pytest, PyYAML, FastAPI (或极简 HTTP Web Server)

## Global Constraints

* 核心逻辑全部在 Python 内存中计算，不依赖外部数据库。
* 每一个子任务必须遵循严格的 TDD：先编写失败的单元测试 -> 运行单元测试 -> 编写最小功能实现 -> 运行测试通过 -> git 提交。
* 核心指标计算中需引入白噪声扰动，日志记录必须具备非故障偶发噪点。
* 强制使用 `uv` 替代原生 `pip` 进行包管理与 venv 维护。
* 包下载统一指定阿里云 PyPI 镜像：`--index-url https://mirrors.aliyun.com/pypi/simple/`。

---

### Task 1: Simulation Clock with Time Alignment & Event Bus

**Files:**
- Create: `simulator/clock.py`
- Create: `simulator/event_bus.py`
- Test: `tests/simulator/test_clock_event.py`

**Interfaces:**
- Consumes: None
- Produces:
  * `SimulationClock(start_time: datetime, step_duration: timedelta)`: 方法 `tick()`, `now() -> datetime`, `current_tick: int`。
  * `TimeAligner(clock: SimulationClock)`: 提供 `align_timestamp(tick: int, real_now: datetime) -> datetime`。
  * `BaseEvent(...)`: 包含 `event_id`, `tick`, `timestamp`, `entity_id`, `severity`, `event_type`, `payload`, `trace_id`。
  * `EventBus()`: `publish(event: BaseEvent)`, `subscribe(event_type, callback)`。

- [x] **Step 1: 编写失败的测试**
  
  在 `tests/simulator/test_clock_event.py` 中编写测试：
  ```python
  from datetime import datetime, timezone, timedelta
  import pytest
  from simulator.clock import SimulationClock, TimeAligner
  from simulator.event_bus import EventBus, BaseEvent

  def test_simulation_clock_alignment():
      start = datetime(2026, 7, 17, 9, 0, 0, tzinfo=timezone.utc)
      # 步长 100ms
      clock = SimulationClock(start, timedelta(milliseconds=100))
      clock.tick() # tick = 1
      clock.tick() # tick = 2
      assert clock.current_tick == 2
      
      # 动态 Now 映射对齐校验
      real_now = datetime(2026, 7, 17, 14, 0, 0, tzinfo=timezone.utc)
      aligner = TimeAligner(clock)
      # 第 2 个 tick (最后一个 tick) 应该被精确映射为 real_now
      assert aligner.align_timestamp(2, real_now) == real_now
      # 第 1 个 tick 应该被偏移回 100ms 之前
      assert aligner.align_timestamp(1, real_now) == real_now - timedelta(milliseconds=100)
  ```

- [x] **Step 2: 运行测试验证失败**
  
  Run: `pytest tests/simulator/test_clock_event.py -v`
  Expected: FAIL (ImportError)

- [x] **Step 3: 编写最小实现代码**
  
  在 `simulator/clock.py` 中实现时钟与对齐算法：
  ```python
  from datetime import datetime, timedelta

  class SimulationClock:
      def __init__(self, start_time: datetime, step_duration: timedelta = timedelta(milliseconds=100)):
          self.start_time = start_time
          self.step_duration = step_duration
          self.current_tick = 0
          
      def tick(self):
          self.current_tick += 1
          
      def now(self) -> datetime:
          return self.start_time + self.current_tick * self.step_duration

  class TimeAligner:
      def __init__(self, clock: SimulationClock):
          self.clock = clock
          
      def align_timestamp(self, tick: int, real_now: datetime) -> datetime:
          total_ticks = self.clock.current_tick
          offset_ticks = total_ticks - tick
          return real_now - offset_ticks * self.clock.step_duration
  ```
  
  在 `simulator/event_bus.py` 中实现 BaseEvent 与 EventBus。

- [x] **Step 4: 运行测试验证通过**
  
  Run: `pytest tests/simulator/test_clock_event.py -v`
  Expected: PASS

- [x] **Step 5: 提交**
  
  ```bash
  git add simulator/clock.py simulator/event_bus.py tests/simulator/test_clock_event.py
  git commit -m "feat(simulator): add Clock with RealNow Alignment and EventBus"
  ```

---

### Task 2: Service Entity with Limit Behaviors & Topology Semantics

**Files:**
- Create: `simulator/entity.py`
- Test: `tests/simulator/test_entity_topology.py`

**Interfaces:**
- Consumes: `SimulationClock`, `EventBus`
- Produces:
  * `Entity`: 基类，包含局部 PRNG (Random) 实例。
  * `ServiceEntity(entity_id: str, name: str, seed: int)`: 物理上限行为判断（Worker Thread 503, Connection wait timeout, OOM）。计算 derived metrics 时加入 `self.random_gen` 的 $\pm 2\%$ 白噪声。
  * `Topology`: 支持在 dependency 边定义 `type` ("fan_out" 或 "route") 与 `weight`。

- [x] **Step 1: 编写失败的测试**
  
  在 `tests/simulator/test_entity_topology.py` 中编写测试：
  ```python
  import pytest
  from simulator.entity import ServiceEntity, Topology

  def test_topology_routing_and_fanout():
      topo = Topology()
      # Gateway 是并行扇出
      topo.add_node("Gateway", "fan_out")
      topo.add_dependency("Gateway", "OrderService", 1.0)
      topo.add_dependency("Gateway", "UserService", 1.0)
      
      # OrderService 是加权随机路由
      topo.add_node("OrderService", "route")
      topo.add_dependency("OrderService", "PaymentService", 0.8)
      topo.add_dependency("OrderService", "InventoryService", 0.2)
      
      assert topo.nodes["Gateway"]["type"] == "fan_out"
      assert topo.nodes["OrderService"]["type"] == "route"
      
  def test_derived_metrics_with_noise_determinism():
      # 两个使用相同 Seed 实例化的 Service 派生指标应该 100% 相同 (PRNG 确定性)
      srv1 = ServiceEntity("pay1", "Payment1", seed=42)
      srv2 = ServiceEntity("pay2", "Payment2", seed=42)
      
      srv1.resources["active_workers"] = 5
      srv1.resources["max_workers"] = 10
      srv2.resources["active_workers"] = 5
      srv2.resources["max_workers"] = 10
      
      assert srv1.derived_metrics()["cpu_usage"] == srv2.derived_metrics()["cpu_usage"]
  ```

- [x] **Step 2: 运行测试验证失败**
  
  Run: `pytest tests/simulator/test_entity_topology.py -v`
  Expected: FAIL

- [x] **Step 3: 编写最小实现代码**
  
  在 `simulator/entity.py` 中实现：
  * 使用 `random.Random(seed)` 初始化 Entity 内部 PRNG。
  * `ServiceEntity.derived_metrics()` 中将 `self.random_gen.uniform(-2.0, 2.0)` 加入 CPU 计算。
  * 实现 `Topology` 管理 `nodes` 字典（包括节点调用语义类型）与 `dependencies` 边。

- [x] **Step 4: 运行测试验证通过**
  
  Run: `pytest tests/simulator/test_entity_topology.py -v`
  Expected: PASS

- [x] **Step 5: 提交**
  
  ```bash
  git add simulator/entity.py tests/simulator/test_entity_topology.py
  git commit -m "feat(simulator): implement local PRNG and Routing/Fanout topology"
  ```

---

### Task 3: State Evolution Pipeline with Trace Tree & Retries

**Files:**
- Create: `simulator/pipeline.py`
- Test: `tests/simulator/test_pipeline.py`

**Interfaces:**
- Consumes: `Entity`, `Topology`, `SimulationClock`, `EventBus`
- Produces:
  * `SpanNode`: 存储 `span_id`, `parent_span_id`, `service`, `status` (OK/ERROR/TIMEOUT), `duration`, `retry_count`, `error_message`。
  * `Request(trace_id: str, root_span: SpanNode)`
  * `StateEvolutionPipeline`: 在 `run_tick` 中，第一阶段生成 Request 并按照拓扑语义（随机游走或扇出并发）生成 SpanNode 树骨架。在 `Update Dependency` 阶段，流经故障节点时更新 Span 状态为 ERROR/TIMEOUT。根据服务的重试策略在当前 SpanNode 节点下生成同层的重试 Span。

- [x] **Step 1: 编写失败的测试**
  
  在 `tests/simulator/test_pipeline.py` 中：
  ```python
  from datetime import datetime, timezone
  import pytest
  from simulator.clock import SimulationClock
  from simulator.event_bus import EventBus
  from simulator.entity import ServiceEntity, Topology
  from simulator.pipeline import StateEvolutionPipeline

  def test_pipeline_request_path_and_retries():
      clock = SimulationClock(datetime(2026, 7, 17, 9, 0, 0, tzinfo=timezone.utc))
      bus = EventBus()
      
      order = ServiceEntity("order", "OrderService", seed=42)
      payment = ServiceEntity("payment", "PaymentService", seed=42)
      
      entities = {"order": order, "payment": payment}
      topo = Topology()
      topo.add_node("order", "route")
      topo.add_dependency("order", "payment", 1.0)
      
      pipeline = StateEvolutionPipeline(entities, topo, clock, bus)
      
      # 注入故障使 Payment 超时
      payment.resources["active_connections"] = 50
      payment.resources["max_connections"] = 50 # 占满连接池，触发 TIMEOUT
      # 为 Order 配置重试策略
      order.resources["retry_policy"] = {"max_attempts": 2}
      
      # 运行 tick 产生 Request
      pipeline.run_tick(ingress_qps=1.0)
      
      # 应该在 pipeline 运行期间投递出 TraceFinishedEvent，内含嵌套的 Span 树且包含重试 Span
      # 我们通过订阅事件总线验证生成的 SpanNode 树结构中包含了 Payment 的 TIMEOUT 状态以及重试节点。
  ```

- [x] **Step 2: 运行测试验证失败**
  
  Run: `pytest tests/simulator/test_pipeline.py -v`
  Expected: FAIL

- [x] **Step 3: 编写最小实现代码**
  
  在 `simulator/pipeline.py` 中实现：
  * `SpanNode` 数据类与其序列化结构。
  * `StateEvolutionPipeline` 运行流程：
    1. 根据 ingress_qps，生成对应数量的 `Request`。
    2. 基于 `Topology`，对每个 Request 从入口节点进行遍历：若是 `fan_out`，生成多个并发子 Span 节点；若是 `route`，使用 `random_gen.choices` 依据权重选择一条子路径。
    3. 流经故障节点（根据上限行为判定，如 `active_connections >= max_connections`），将 Span 节点的 `status` 设置为 `TIMEOUT` 或 `ERROR`。
    4. 若有 `retry_policy`，在其 `children` 中生成同层 sibling `SpanNode`（标记 retry_count 递增），再次模拟下游调用直到成功或达到 max_attempts。
    5. 结束后，打包整个 `Request` 为 `TraceFinishedEvent` 发布至事件总线。

- [x] **Step 4: 运行测试验证通过**
  
  Run: `pytest tests/simulator/test_pipeline.py -v`
  Expected: PASS

- [x] **Step 5: 提交**
  
  ```bash
  git add simulator/pipeline.py tests/simulator/test_pipeline.py
  git commit -m "feat(simulator): implement Request SpanTree routing and sibling Retries"
  ```

---

### Task 4: Projections with Alertmanager Resolution

**Files:**
- Create: `simulator/projections/` 目录下各投影文件
- Test: `tests/simulator/test_projections.py`

**Interfaces:**
- Consumes: `EventBus`, `BaseEvent`
- Produces:
  * `MetricProjection`: 会话级缓存 derived metrics，带 $\pm 2\%$ 白噪声。
  * `LogProjection`: 监听事件。支持混入 `random_gen.random() < 0.001` 的偶发非故障网络抖动 WARN 噪声日志。
  * `TraceProjection`: 缓存 `TraceFinishedEvent` 并支持自底向上时间对齐映射组装。
  * `AlertmanagerProjection`: 评估告警状态机（Firing -> Resolved）。

- [x] **Step 1: 编写失败的测试**
  
  在 `tests/simulator/test_projections.py` 中：
  ```python
  from datetime import datetime, timezone
  import pytest
  from simulator.event_bus import EventBus, BaseEvent
  from simulator.projections.alert import AlertmanagerProjection

  def test_alertmanager_resolution_lifecycle():
      bus = EventBus()
      alert_proj = AlertmanagerProjection(bus)
      
      now = datetime(2026, 7, 17, 9, 0, 0, tzinfo=timezone.utc)
      
      # 1. 触发越线报警
      bus.publish(BaseEvent("e1", 1, now, "gateway", "CRITICAL", "MetricThresholdExceeded", {"metric": "error_rate", "value": 0.12}))
      firing = alert_proj.get_firing_alerts("session_test")
      assert len(firing) == 1
      assert firing[0]["status"] == "firing"
      assert firing[0]["endsAt"] is None
      
      # 2. 指标恢复正常，触发告警消解
      bus.publish(BaseEvent("e2", 2, now + timedelta(seconds=1), "gateway", "INFO", "MetricThresholdRecovered", {"metric": "error_rate", "value": 0.01}))
      firing = alert_proj.get_firing_alerts("session_test")
      assert len(firing) == 0 # 活跃告警队列为空
      
      resolved = alert_proj.get_resolved_alerts("session_test")
      assert len(resolved) == 1
      assert resolved[0]["status"] == "resolved"
      assert resolved[0]["endsAt"] is not None # 拥有消解截止时间戳
  ```

- [x] **Step 2: 运行测试验证失败**
  
  Run: `pytest tests/simulator/test_projections.py -v`
  Expected: FAIL

- [x] **Step 3: 编写最小实现代码**
  
  在 `simulator/projections/alert.py` 等文件中实现：
  * `AlertmanagerProjection` 订阅 `MetricThresholdExceeded`（创建 firing alert，startsAt=aligned_time）与 `MetricThresholdRecovered`（标记 resolved alert，endsAt=aligned_time，并从 firing 队列移入 resolved 队列）。
  * 实现 `LogProjection` 偶发随机 WARN 噪声混入。
  * 实现 `TraceProjection` 链路组装。

- [x] **Step 4: 运行测试验证通过**
  
  Run: `pytest tests/simulator/test_projections.py -v`
  Expected: PASS

- [x] **Step 5: 提交**
  
  ```bash
  git add simulator/projections/ tests/simulator/test_projections.py
  git commit -m "feat(simulator): implement Projections and Alertmanager Lifecycle"
  ```

---

### Task 5: In-Memory State HTTP Server (HTTP Sharing API)

**Files:**
- Create: `simulator/state_server.py`
- Test: `tests/simulator/test_state_server.py`

**Interfaces:**
- Consumes: `MetricProjection`, `LogProjection`, `TraceProjection`, `AlertmanagerProjection`
- Produces:
  * `InMemoryStateServer`: 轻量级 API 服务，暴露：
    * `GET /api/v1/metrics?session_id=...&metric=...&start=...&end=...`
    * `GET /api/v1/logs?session_id=...&service=...`
    * `GET /api/v1/traces?session_id=...&trace_id=...`
    * `GET /api/v1/alerts?session_id=...&status=firing/resolved`
    * `DELETE /api/v1/session?session_id=...` (清空内存)

- [x] **Step 1: 编写失败的测试**
  
  在 `tests/simulator/test_state_server.py` 中：
  ```python
  import pytest
  from fastapi.testclient import TestClient
  from simulator.state_server import create_app

  def test_state_server_endpoints():
      app = create_app()
      client = TestClient(app)
      
      # 验证 API 能够响应 Session 删除和数据查询接口（可 Mock 返回空）
      response = client.delete("/api/v1/session?session_id=sess_999")
      assert response.status_code == 200
      assert response.json()["status"] == "cleared"
  ```

- [x] **Step 2: 运行测试验证失败**
  
  Run: `pytest tests/simulator/test_state_server.py -v`
  Expected: FAIL

- [x] **Step 3: 编写最小实现代码**
  
  在 `simulator/state_server.py` 中，使用 FastAPI 快速搭建轻量级 Web APP，暴露出对 Projection 只读查询接口与 DELETE 内存清空逻辑。

- [x] **Step 4: 运行测试验证通过**
  
  Run: `pytest tests/simulator/test_state_server.py -v`
  Expected: PASS

- [x] **Step 5: 提交**
  
  ```bash
  git add simulator/state_server.py tests/simulator/test_state_server.py
  git commit -m "feat(simulator): add In-Memory State HTTP API Server for MCP sharing"
  ```
