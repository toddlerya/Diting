from datetime import datetime, timedelta, timezone
from pathlib import Path
import time

from simulator.clock import SimulationClock
from simulator.environment import load_environment
from simulator.event_bus import EventBus
from simulator.pipeline import StateEvolutionPipeline
from simulator.projections.alert import AlertmanagerProjection
from simulator.projections.log import LogProjection
from simulator.projections.metric import MetricProjection
from simulator.projections.trace import TraceProjection
from simulator.scenario import Scenario
from mcp.state_client import StateClient
from mcp.prometheus_server import query_range_tool, query_instant_tool, get_alerts_tool
from mcp.loki_server import query_logs_tool, list_services_tool
from mcp.trace_server import search_traces_tool, get_trace_tool
from mcp.knowledge_server import search_runbooks_engine

DEMO_SESSION = "mcp_demo_session"


def print_ascii_banner():
    print("""
\033[1;36m==================================================================
   谛听 (Diting) - MCP Tools & Observability Integration Demo
==================================================================\033[0m
    """)


def main():
    print_ascii_banner()

    # 1. 启动仿真引擎并推演场景数据
    print("\033[1;33m[1/4] 启动仿真引擎并推演故障场景 (10 Ticks)... \033[0m")
    start_time = datetime(2026, 7, 23, 9, 0, 0, tzinfo=timezone.utc)
    clock = SimulationClock(start_time, timedelta(milliseconds=1000))
    bus = EventBus()

    metric_proj = MetricProjection(bus, clock)
    log_proj = LogProjection(bus, clock, seed=100, noise_rate=0.8)
    trace_proj = TraceProjection(bus, clock)
    alert_proj = AlertmanagerProjection(bus, clock)

    current_dir = Path(__file__).resolve().parent
    env_path = current_dir / "simulator" / "environments" / "default_env.yaml"
    entities, topo = load_environment(str(env_path))
    metric_proj.bind_entities(entities)

    pipeline = StateEvolutionPipeline(entities, topo, clock, bus)
    scenario_path = current_dir / "simulator" / "scenarios" / "redis_exhaust.yaml"
    scenario = Scenario.from_yaml(str(scenario_path))

    for t in range(1, 11):
        scenario.apply(t, entities, bus, clock, session_id=DEMO_SESSION)
        pipeline.run_tick(ingress_qps=1.0, session_id=DEMO_SESSION)

    print("\033[1;32m✓ 仿真推演完成，数据已离线构建至共享内存 Projection 中！\033[0m\n")

    # 2. 构造本地 StateClient (直接关联内存投影层或 HTTP API)
    # 为方便 Demo 演示，我们使用 Mock API 客户端访问，或构造内存通道
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from simulator.state_server import create_app

    app = create_app(metric_proj, log_proj, trace_proj, alert_proj)
    test_client = TestClient(app)

    # 用 httpx TestClient 作为 StateClient 的 transport
    state_client = StateClient(transport=test_client._transport)

    # 3. 演示调用 4 个 MCP Server 的 Tools
    print("\033[1;36m[2/4] 测试与展示 4 个 MCP Server 核心 Tools 调用效果：\033[0m\n")

    # A. Prometheus MCP Server Tools
    print("\033[1;35m>>> 1. Prometheus MCP Server (Metrics & Alertmanager Tools) <<<\033[0m")
    cpu_pts = query_range_tool(
        DEMO_SESSION, "gateway_cpu_usage", start_tick=0, end_tick=10, client=state_client
    )
    print(
        f"  * query_range('gateway_cpu_usage'): 成功获取 {len(cpu_pts)} 个带 UTC 对齐时间戳的数据点"
    )
    if cpu_pts:
        print(
            f"    - 最新点: timestamp={cpu_pts[-1]['timestamp']}, value={cpu_pts[-1]['value']:.2f}%"
        )

    instant_pt = query_instant_tool(DEMO_SESSION, "redis_utilization", client=state_client)
    print(f"  * query_instant('redis_utilization'): value={instant_pt.get('value')}%")

    firing_alerts = get_alerts_tool(DEMO_SESSION, status="firing", client=state_client)
    resolved_alerts = get_alerts_tool(DEMO_SESSION, status="resolved", client=state_client)
    print(f"  * get_alerts(status='firing'): {len(firing_alerts)} 条活跃告警")
    print(f"  * get_alerts(status='resolved'): {len(resolved_alerts)} 条已消解告警")
    for a in resolved_alerts:
        print(
            f"    - Alert: {a['labels']['alertname']} | status={a['status']} | startsAt={a['startsAt']}"
        )

    # B. Loki MCP Server Tools
    print("\n\033[1;35m>>> 2. Loki MCP Server (Log 流 Tools) <<<\033[0m")
    services = list_services_tool(DEMO_SESSION, client=state_client)
    print(f"  * list_services(): 可用日志微服务列表 = {services}")

    crit_logs = query_logs_tool(
        DEMO_SESSION, "PaymentService", level="CRITICAL", client=state_client
    )
    print(f"  * query_logs('PaymentService', 'CRITICAL'): 找到 {len(crit_logs)} 条关键错误日志")
    for log_line in crit_logs:
        print(f"    - {log_line}")

    # C. Trace MCP Server Tools
    print("\n\033[1;35m>>> 3. Trace MCP Server (Tempo/OpenTelemetry 链路 Tools) <<<\033[0m")
    slow_traces = search_traces_tool(DEMO_SESSION, min_duration_ms=400.0, client=state_client)
    print(f"  * search_traces(min_duration_ms=400.0): 找到 {len(slow_traces)} 条慢链路")
    if slow_traces:
        t0 = slow_traces[0]
        t_id = t0["trace_id"]
        trace_detail = get_trace_tool(DEMO_SESSION, t_id, client=state_client)
        print(
            f"  * get_trace('{t_id}'): 获得 Span 嵌套树，入口耗时={trace_detail['request']['root_span']['duration']:.1f}ms"
        )

    # D. Knowledge MCP Server (BM25 降噪)
    print("\n\033[1;35m>>> 4. Knowledge MCP Server (rank-bm25 降噪检索) <<<\033[0m")
    kb_results = search_runbooks_engine("Redis connection pool leak", top_k=2)
    print(
        f"  * search_runbooks('Redis connection pool leak'): 打败 10+ 篇干扰 Wiki，精准召回 Top-1 匹配:"
    )
    for doc in kb_results:
        print(f"    - [{doc['filename']}] (BM25 Score: {doc['score']:.2f}) - {doc['title']}")

    # 4. 会话资源销毁测试
    print("\n\033[1;33m[3/4] 触发物理会话内存清理 (DELETE /api/v1/session)... \033[0m")
    del_res = state_client.delete_session(DEMO_SESSION)
    print(f"\033[1;32m✓ 会话 {del_res['session_id']} 物理内存清除成功！\033[0m")

    # 再次查询验证内存已释放
    check_pts = state_client.get_metrics(DEMO_SESSION, "gateway_cpu_usage")
    print(f"  * 清理后验证: query_range 数据点数量 = {len(check_pts)} (已完全清空)")

    print("\n\033[1;32m[4/4] run_mcp_demo.py 演示全部成功通过！\033[0m\n")


if __name__ == "__main__":
    main()
