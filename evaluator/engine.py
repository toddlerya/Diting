import os

from evaluator.anti_hallucination import AntiHallucinationEvaluator
from evaluator.efficiency import EfficiencyEvaluator
from evaluator.path_recall import PathRecallEvaluator
from evaluator.root_cause import RootCauseEvaluator
from evaluator.schema import EvaluationScorecard, GroundTruth
from runtime.schema import BlackboardState
from simulator.scenario import Scenario


class EvaluatorEngine:
    def __init__(self, pass_threshold: float = 60.0):
        self.pass_threshold = pass_threshold
        self.root_cause_eval = RootCauseEvaluator()
        self.path_recall_eval = PathRecallEvaluator()
        self.anti_hallucination_eval = AntiHallucinationEvaluator()
        self.efficiency_eval = EfficiencyEvaluator()

    def evaluate(self, state: BlackboardState, scenario: Scenario) -> EvaluationScorecard:
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
        """若存在 LangFuse API key，可选进行轨迹与得分同步。"""
        if os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
            try:
                # Placeholder for optional LangFuse client log
                pass
            except ImportError:
                pass
