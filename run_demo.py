import uvicorn
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict
from simulator.clock import SimulationClock
from simulator.event_bus import EventBus, BaseEvent
from simulator.environment import load_environment
from simulator.pipeline import StateEvolutionPipeline
from simulator.projections.metric import MetricProjection
from simulator.projections.log import LogProjection
from simulator.projections.trace import TraceProjection
from simulator.projections.alert import AlertmanagerProjection
from simulator.state_server import create_app
from simulator.scenario import Scenario

def print_ascii_art():
    print("""
\033[1;36m==================================================================
   谛听 (Diting) - Agent AIOps Simulation & Evaluation Platform
==================================================================\033[0m
    """)

def main():
    print_ascii_art()

    # 1. 初始化时钟与事件总线
    start_time = datetime(2026, 7, 17, 9, 0, 0, tzinfo=timezone.utc)
    clock = SimulationClock(start_time, timedelta(milliseconds=1000))
    bus = EventBus()

    # 2. 初始化投影层
    metric_proj = MetricProjection(bus, clock)
    log_proj = LogProjection(bus, clock, seed=100, noise_rate=0.8) # 固定噪点种子并高配噪声以供 Demo 稳定输出
    trace_proj = TraceProjection(bus, clock)
    alert_proj = AlertmanagerProjection(bus, clock)

    # 3. 从 YAML 动态加载声明式测试环境拓扑与服务实体
    current_dir = Path(__file__).resolve().parent
    env_path = current_dir / "simulator" / "environments" / "default_env.yaml"
    entities, topo = load_environment(str(env_path))

    # 订阅 Finished Trace 以同步录入 metrics 投影
    def sync_projections(event):
        req = event.payload["request"]
        session_id = event.payload.get("session_id", "demo_session")
        # 记录各组件的派生指标
        for s_id, entity in entities.items():
            metrics = entity.derived_metrics()
            if metrics:
                # 记录微服务指标 (CPU / Latency)
                if "cpu_usage" in metrics:
                    metric_proj.record_metric(session_id, f"{s_id}_cpu_usage", event.tick, metrics["cpu_usage"])
                if "latency" in metrics:
                    metric_proj.record_metric(session_id, f"{s_id}_latency", event.tick, metrics["latency"])
                # 记录基础设施指标 (Utilization)
                if "utilization" in metrics:
                    metric_proj.record_metric(session_id, f"{s_id}_utilization", event.tick, metrics["utilization"])

    bus.subscribe("TraceFinishedEvent", sync_projections)

    # 4. 创建演进流水线并加载剧本
    pipeline = StateEvolutionPipeline(entities, topo, clock, bus)

    current_dir = Path(__file__).resolve().parent
    scenario_path = current_dir / "simulator" / "scenarios" / "redis_exhaust.yaml"
    scenario = Scenario.from_yaml(str(scenario_path))

    print("\033[1;33m[1/3] 开始运行仿真引擎推演 (10 Ticks)... \033[0m")

    # 循环演进 10 个 tick
    for t in range(1, 11):
        # 1. 打印控制台故障提示
        if t == 4:
            print(f"\n\033[1;31m[Tick {t}] >>> 注入故障：Redis 物理连接池满 (50/50) <<< \033[0m")
        elif t == 8:
            print(f"\n\033[1;32m[Tick {t}] >>> 故障自愈消解：释放 Redis 连接数 (5/50) <<< \033[0m")

        # 2. 应用 YAML 剧本配置的状态变更和故障注入
        scenario.apply(t, entities, bus, clock, session_id="demo_session")

        # 3. 推演：运行 tick 演进（推进时钟）
        pipeline.run_tick(ingress_qps=1.0, session_id="demo_session")

        time.sleep(0.02) # 极快推演

    print("\033[1;32m推演完成！\033[0m\n")

    # 5. 格式化输出数据结构效果
    real_now = datetime.now(timezone.utc)
    print("\033[1;36m[2/3] --- 可观测性投影数据可视化 (已对齐物理现实 Now) ---\033[0m")

    # A. 打印 Trace 嵌套结构与重试
    print("\n\033[1;35m>>> 1. Jaeger 分布式 Trace (嵌套树 + Sibling 重试) <<<\033[0m")
    traces = trace_proj.query_traces("demo_session", real_now)
    # 取出故障时间段的 Trace (Tick 4 后的一个 Trace)
    # 我们以文字缩进打印
    def print_span(span, indent=0):
        pre = "  " * indent
        retry_flag = f" [Attempt #{span.retry_count + 1}]" if span.retry_count > 0 else ""
        color = "\033[31m" if span.status != "OK" else "\033[32m"
        print(f"{pre}└─ {span.service}{retry_flag} -> Status: {color}{span.status}\033[0m {span.error_message}")
        for child in span.children:
            print_span(child, indent + 2)

    # 打印最后一个 trace 状态 (即最后产生的链路)
    if traces:
        last_trace = traces[-1]
        print(f"Trace ID: {last_trace['trace_id']}")
        print(f"Aligned Timestamp: {last_trace['timestamp']}")
        print_span(last_trace["request"].root_span)

    # B. 打印日志与白噪声
    print("\n\033[1;35m>>> 2. Loki 日志流 (故障日志 + 警告背景噪声) <<<\033[0m")
    err_logs = log_proj.query_logs("demo_session", "PaymentService", "CRITICAL", real_now)
    warn_logs = log_proj.query_logs("demo_session", "PaymentService", "WARNING", real_now)
    print("CRITICAL 级故障日志:")
    for log in err_logs:
        print(f"  {log}")
    print("WARNING 级偶发杂噪日志:")
    for log in warn_logs[:2]: # 打印一两条噪点
        print(f"  {log}")

    # C. 打印 Alertmanager 生命周期
    print("\n\033[1;35m>>> 3. Alertmanager 告警生命周期 (Firing & Resolved) <<<\033[0m")
    print("Resolved 告警列表 (历史):")
    for a in alert_proj.get_resolved_alerts("demo_session", real_now):
        print(f"  Alertname: {a['labels']['alertname']} | Status: \033[32m{a['status']}\033[0m | startsAt: {a['startsAt']} | endsAt: {a['endsAt']}")

    # 6. 启动 API 服务
    import argparse
    import socket

    parser = argparse.ArgumentParser(description="Diting Demo Launcher")
    parser.add_argument("--port", type=int, default=8000, help="API Server port (default: 8000)")
    args = parser.parse_args()

    port = args.port
    # 探测端口可用性，占用时自增
    for attempt in range(50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                # 绑定成功，释放占用以供 uvicorn 使用
                break
            except OSError:
                print(f"\033[1;31m端口 {port} 已被占用，正在自动尝试下一个端口...\033[0m")
                port += 1
    else:
        print("\033[1;31m未找到可用端口，无法拉起 API Server。\033[0m")
        return

    print(f"\n\033[1;33m[3/3] 启动 In-Memory State HTTP Server API (Port: {port}) ... \033[0m")
    print("服务运行后，可通过如下接口进行多会话隔离查询：")
    print(f"  * Metrics 查询 (CPU): http://127.0.0.1:{port}/api/v1/metrics?session_id=demo_session&metric=gateway_cpu_usage")
    print(f"  * Metrics 查询 (Redis): http://127.0.0.1:{port}/api/v1/metrics?session_id=demo_session&metric=redis_utilization")
    print(f"  * Logs 查询: http://127.0.0.1:{port}/api/v1/logs?session_id=demo_session&service=PaymentService&level=CRITICAL")
    print(f"  * Traces 查询: http://127.0.0.1:{port}/api/v1/traces?session_id=demo_session")
    print(f"  * Alerts 状态: http://127.0.0.1:{port}/api/v1/alerts?session_id=demo_session&status=resolved")
    print("\033[1;32m本地 Server 即将拉起，按 Ctrl + C 可终止程序。\033[0m\n")

    app = create_app(metric_proj, log_proj, trace_proj, alert_proj)
    uvicorn.run(app, host="127.0.0.1", port=port)

if __name__ == "__main__":
    main()
