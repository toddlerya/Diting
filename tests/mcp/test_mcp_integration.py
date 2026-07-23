import warnings
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from mcp.knowledge_server import search_runbooks_engine
from mcp.loki_server import list_services_tool, query_logs_tool
from mcp.prometheus_server import get_alerts_tool, query_instant_tool, query_range_tool
from mcp.state_client import StateClient
from mcp.trace_server import get_trace_tool, search_traces_tool
from simulator.clock import SimulationClock
from simulator.environment import load_environment
from simulator.event_bus import EventBus
from simulator.pipeline import StateEvolutionPipeline
from simulator.projections.alert import AlertmanagerProjection
from simulator.projections.log import LogProjection
from simulator.projections.metric import MetricProjection
from simulator.projections.trace import TraceProjection
from simulator.scenario import Scenario
from simulator.state_server import create_app

DEMO_SESSION = "mcp_integration_test_session"


def test_mcp_full_integration_flow():
    """全流程 MCP 集成测试：从仿真推演、State Server 构建到 4 大 MCP Tools 响应校验"""
    warnings.filterwarnings("ignore", category=DeprecationWarning)

    # 1. 初始化物理引擎与 Projection 监听
    start_time = datetime(2026, 7, 23, 9, 0, 0, tzinfo=UTC)
    clock = SimulationClock(start_time, timedelta(milliseconds=1000))
    bus = EventBus()

    metric_proj = MetricProjection(bus, clock)
    log_proj = LogProjection(bus, clock, seed=100, noise_rate=0.8)
    trace_proj = TraceProjection(bus, clock)
    alert_proj = AlertmanagerProjection(bus, clock)

    current_dir = Path(__file__).resolve().parent.parent.parent
    env_path = current_dir / "simulator" / "environments" / "default_env.yaml"
    entities, topo = load_environment(str(env_path))
    metric_proj.bind_entities(entities)

    pipeline = StateEvolutionPipeline(entities, topo, clock, bus)
    scenario_path = current_dir / "simulator" / "scenarios" / "redis_exhaust.yaml"
    scenario = Scenario.from_yaml(str(scenario_path))

    # 2. 模拟 10 个 Ticks 演进与故障注入
    for t in range(1, 11):
        scenario.apply(t, entities, bus, clock, session_id=DEMO_SESSION)
        pipeline.run_tick(ingress_qps=1.0, session_id=DEMO_SESSION)

    # 3. 构建物理状态 HTTP 服务客户端
    app = create_app(metric_proj, log_proj, trace_proj, alert_proj)
    test_client = TestClient(app)
    state_client = StateClient(transport=test_client._transport)

    # 4. 校验 Prometheus MCP Server Tools
    cpu_pts = query_range_tool(
        DEMO_SESSION, "gateway_cpu_usage", start_tick=0, end_tick=10, client=state_client
    )
    assert len(cpu_pts) > 0, "Prometheus query_range 应能查到 CPU 指标数据"

    instant_pt = query_instant_tool(DEMO_SESSION, "redis_utilization", client=state_client)
    assert instant_pt.get("value") is not None, "Prometheus query_instant 应返回 Redis 利用率"

    firing_alerts = get_alerts_tool(DEMO_SESSION, status="firing", client=state_client)
    resolved_alerts = get_alerts_tool(DEMO_SESSION, status="resolved", client=state_client)
    assert isinstance(firing_alerts, list)
    assert isinstance(resolved_alerts, list)

    # 5. 校验 Loki MCP Server Tools
    services = list_services_tool(DEMO_SESSION, client=state_client)
    assert "PaymentService" in services, "Loki list_services 应包含 PaymentService"

    crit_logs = query_logs_tool(
        DEMO_SESSION, "PaymentService", level="CRITICAL", client=state_client
    )
    assert len(crit_logs) > 0, "Loki query_logs 应能查到 PaymentService 的 CRITICAL 日志"

    # 6. 校验 Trace MCP Server Tools
    slow_traces = search_traces_tool(DEMO_SESSION, min_duration_ms=400.0, client=state_client)
    assert len(slow_traces) > 0, "Trace search_traces 应找到耗时超过 400ms 的慢链路"

    t_id = slow_traces[0]["trace_id"]
    trace_detail = get_trace_tool(DEMO_SESSION, t_id, client=state_client)
    assert trace_detail is not None, "Trace get_trace 应查到指定 trace_id 的详细 Span 结构"

    # 7. 校验 Knowledge MCP Server Tools
    kb_results = search_runbooks_engine("Redis connection pool leak", top_k=2)
    assert len(kb_results) > 0, "Knowledge BM25 应检索出 Runbook 文档"
    assert "redis" in kb_results[0]["filename"].lower()

    # 8. 会话清理逻辑校验
    del_res = state_client.delete_session(DEMO_SESSION)
    assert del_res["session_id"] == DEMO_SESSION

    check_pts = state_client.get_metrics(DEMO_SESSION, "gateway_cpu_usage")
    assert len(check_pts) == 0, "清理会话后 metrics 数据点应归零"
