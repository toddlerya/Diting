# run_eval_demo.py
import tempfile

from evaluator.engine import EvaluatorEngine
from runtime.graph import run_diagnosis_workflow
from simulator.scenario import Scenario


def main():
    print("=" * 60)
    print("🐕 Diting (谛听) - Evaluation Engine E2E Demo")
    print("=" * 60)

    # 1. 动态生成带有 Ground Truth 节的场景 YAML 文件，验证 Scenario.from_yaml(...) 全链路
    sc_yaml_content = """
name: payment_redis_exhaust_cascade
description: PaymentService Redis Connection Pool Exhaustion Cascade Failure
seed: 42
ground_truth:
  root_cause_service: PaymentService
  root_cause_entity: PaymentService-RedisPool
  failure_type: REDIS_POOL_LEAK
  expected_tools:
    - query_metrics
    - query_logs
  expected_services:
    - Gateway
    - PaymentService
  timeline:
    - tick: 10
      entity_id: PaymentService
      metric_name: active_connections
      expected_value: 50.0
      expected_timestamp: "2026-07-27T00:00:10+00:00"
      log_keyword: Timeout waiting for connection
steps: []
"""
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(sc_yaml_content)
        temp_path = f.name

    print("\n[1/3] Loading Scenario via Scenario.from_yaml()...")
    scenario = Scenario.from_yaml(temp_path)
    print(f"  - Loaded Scenario Name: {scenario.name}")
    print(
        f"  - Ground Truth Root Cause Entity: {scenario.ground_truth_data.get('root_cause_entity')}"
    )

    # 2. 模拟 Firing Alert 触发展开 LangGraph 故障诊断
    alert = {
        "alert_name": "HighServiceLatency",
        "service": "Gateway",
        "severity": "CRITICAL",
    }
    print("\n[2/3] Running LangGraph Multi-Agent Diagnosis Workflow...")
    final_state = run_diagnosis_workflow(alert, thread_id="eval-demo-thread")

    report = final_state.get("diagnosis_report")
    if report:
        print("  - Diagnosis Completed. Report Summary:")
        print(f"    * Root Cause Entity : {report.root_cause_entity}")
        print(f"    * Failure Type      : {report.failure_type}")
        print(f"    * Confidence Score  : {report.confidence:.2f}")

    # 3. 运行 EvaluatorEngine 自动化打分
    print("\n[3/3] Running EvaluatorEngine Benchmark Evaluation...")
    engine = EvaluatorEngine(pass_threshold=60.0)
    scorecard = engine.evaluate(final_state, scenario)

    print("\n" + "=" * 60)
    print("📊 BENCHMARK EVALUATION SCORECARD")
    print("=" * 60)
    print(f"Scenario Name       : {scorecard.scenario_name}")
    print(f"Total Benchmark Score: {scorecard.total_score:.1f} / 100.0")
    print(f"Evaluation Status   : {scorecard.status}")
    print("-" * 60)
    print(
        f"  - Root Cause (40%) : {scorecard.root_cause_score.weighted_score:.1f} pts (Raw: {scorecard.root_cause_score.raw_score * 100:.0f}%)"
    )
    print(
        f"  - Path Recall (25%): {scorecard.path_recall_score.weighted_score:.1f} pts (Raw: {scorecard.path_recall_score.raw_score * 100:.0f}%)"
    )
    print(
        f"  - Anti-Hallucination(25%): {scorecard.anti_hallucination_score.weighted_score:.1f} pts (Raw: {scorecard.anti_hallucination_score.raw_score * 100:.0f}%)"
    )
    print(
        f"  - Efficiency (10%) : {scorecard.efficiency_score.weighted_score:.1f} pts (Raw: {scorecard.efficiency_score.raw_score * 100:.0f}%)"
    )
    print("=" * 60)


if __name__ == "__main__":
    main()
