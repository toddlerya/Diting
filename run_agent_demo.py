import json
import warnings
from datetime import UTC, datetime

from runtime.graph import build_diagnosis_graph


def print_ascii_banner():
    print("""
\033[1;36m==================================================================
   谛听 (Diting) - LangGraph Multi-Agent Agent Runtime Demo (Day 5)
==================================================================\033[0m
    """)


def main():
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    print_ascii_banner()

    # 1. 模拟微服务告警接入
    print("\033[1;33m[1/3] 收到监控警报 (Alert Ingress)... \033[0m")
    alert_event = {
        "alert_id": "ALT-20260724-001",
        "alert_name": "HighCpuUsageAndLatencySpike",
        "service": "order-service",
        "severity": "CRITICAL",
        "timestamp": datetime.now(UTC).isoformat(),
        "trace_id": "tr-88902",
        "description": "OrderService container CPU usage > 90%, response latency > 2000ms",
    }
    print(json.dumps(alert_event, indent=2, ensure_ascii=False))
    print("\033[1;32m✓ 告警解析完成，启动 LangGraph 状态机... \033[0m\n")

    # 2. 执行 LangGraph 多 Agent 黑板协同诊断流
    print("\033[1;33m[2/3] 执行 LangGraph Multi-Agent Blackboard Diagnosis Workflow... \033[0m")
    thread_id = "demo-incident-session-001"
    graph = build_diagnosis_graph()
    initial_state = {
        "messages": [],
        "incident_alert": alert_event,
        "suspect_entities": [alert_event.get("service", "unknown-service")],
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

    # 3. 输出黑板统计与阶段细节
    print("\033[1;32m✓ LangGraph 状态图演进完成！\033[0m")
    print(f"  • 总轮次 (Total Rounds): {final_state['current_round'] - 1}")
    print(f"  • 最终状态 (Status): {final_state['status']}")
    print(f"  • 归集证据数 (Evidences Count): {len(final_state['evidences'])}")
    print(f"  • 匹配 Runbooks (Runbooks Count): {len(final_state['matched_runbooks'])}\n")

    print("\033[1;35m--- 黑板证据链清单 (Evidences Collected) ---\033[0m")
    for idx, ev in enumerate(final_state["evidences"], 1):
        print(
            f"  [{idx}] [{ev.source.upper()}] Entity: \033[1m{ev.entity_id}\033[0m | Summary: {ev.summary}"
        )
    print()

    # 4. 打印最终结构化诊断报告
    report = final_state["diagnosis_report"]
    print("\033[1;36m==================================================================")
    print("                     最终根因诊断报告 (RCA Report)")
    print("==================================================================\033[0m")
    if report:
        print(f" \033[1;31m▶ 根因实体 (Root Cause Entity):\033[0m {report.root_cause_entity}")
        print(f" \033[1;31m▶ 故障类型 (Failure Type):\033[0m {report.failure_type}")
        print(f" \033[1;32m▶ 置信度 (Confidence):\033[0m {report.confidence * 100:.1f}%")
        print(f" \033[1;34m▶ 支撑证据 IDs (Evidence IDs):\033[0m {', '.join(report.evidence_ids)}")
        print(f" \033[1;33m▶ 根因摘要 (Summary):\033[0m {report.summary}")
        print(" \033[1;35m▶ 建议止血措施 (Recommended Actions):\033[0m")
        for act in report.recommended_actions:
            print(f"    - {act}")
    print("\033[1;36m==================================================================\033[0m\n")

    # 5. 验证 MemorySaver Checkpointer 快照检索
    print("\033[1;33m[3/3] 验证 Checkpointer 恢复与审计回溯... \033[0m")
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = graph.get_state(config)
    print(f"\033[1;32m✓ 成功恢复 Checkpointer 快照 (thread_id={thread_id})！\033[0m")
    print(f"  • 快照状态: {snapshot.values['status']}")
    print(f"  • 快照根因实体: {snapshot.values['diagnosis_report'].root_cause_entity}\n")


if __name__ == "__main__":
    main()
