"""评估器核心引擎模块。

整合根因准度、路径召回、幻觉抑制及诊断效率四个单维度评估器，
对 Agent Runtime 在指定 Scenario 下的 BlackboardState 进行全面评测并输出综合成绩单 (EvaluationScorecard)。
"""

import os

from evaluator.anti_hallucination import AntiHallucinationEvaluator
from evaluator.efficiency import EfficiencyEvaluator
from evaluator.path_recall import PathRecallEvaluator
from evaluator.root_cause import RootCauseEvaluator
from evaluator.schema import EvaluationScorecard, GroundTruth
from runtime.schema import BlackboardState
from simulator.scenario import Scenario


class EvaluatorEngine:
    """综合评估引擎。

    组合四个单维度评估器并按设定权重汇总出综合得分，决定是否满足通过阈值。
    """

    def __init__(self, pass_threshold: float = 60.0):
        """初始化评估引擎。

        Args:
            pass_threshold: 判定基线通过的分数阈值 (默认 60.0 分)。
        """
        self.pass_threshold = pass_threshold
        self.root_cause_eval = RootCauseEvaluator()
        self.path_recall_eval = PathRecallEvaluator()
        self.anti_hallucination_eval = AntiHallucinationEvaluator()
        self.efficiency_eval = EfficiencyEvaluator()

    def evaluate(self, state: BlackboardState, scenario: Scenario) -> EvaluationScorecard:
        """根据 Agent 黑板状态及测试场景基准真值生成综合评测报告。

        Args:
            state: Agent 排查诊断结束后的黑板状态 BlackboardState。
            scenario: 当前运行的仿真故障场景 Scenario。

        Returns:
            汇总四维加权得分与判定状态的 EvaluationScorecard。
        """
        gt = GroundTruth.from_scenario(scenario)
        report = state.get("diagnosis_report")

        rc_score = self.root_cause_eval.evaluate(report, gt)
        pr_score = self.path_recall_eval.evaluate(state, gt)
        ah_score = self.anti_hallucination_eval.evaluate(state, gt)
        eff_score = self.efficiency_eval.evaluate(state, gt)

        total_score = (
            rc_score.weighted_score
            + pr_score.weighted_score
            + ah_score.weighted_score
            + eff_score.weighted_score
        )

        status = "PASSED" if total_score >= self.pass_threshold else "FAILED"
        summary = (
            f"Benchmark Scorecard for {scenario.name}: Total Score = {total_score:.1f}/100 "
            f"(Status: {status}). Root Cause: {rc_score.raw_score * 100:.0f}%, "
            f"Path Recall: {pr_score.raw_score * 100:.0f}%, "
            f"Anti-Hallucination: {ah_score.raw_score * 100:.0f}%, "
            f"Efficiency: {eff_score.raw_score * 100:.0f}%."
        )

        scorecard = EvaluationScorecard(
            scenario_name=scenario.name,
            root_cause_score=rc_score,
            path_recall_score=pr_score,
            anti_hallucination_score=ah_score,
            efficiency_score=eff_score,
            total_score=round(total_score, 2),
            pass_threshold=self.pass_threshold,
            status=status,
            summary=summary,
        )

        # Post-MVP: LangFuse Progressive Enhancement
        self._maybe_log_langfuse(scorecard)

        return scorecard

    def _maybe_log_langfuse(self, scorecard: EvaluationScorecard) -> None:
        """若环境变量中配置了 LangFuse 凭证，尝试将评测结果同步至 LangFuse。"""
        if os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
            try:
                # Placeholder for optional LangFuse client log
                pass
            except ImportError:
                pass
