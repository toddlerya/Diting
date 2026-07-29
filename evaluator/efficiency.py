"""诊断效率评估器 (Efficiency Evaluator)。

根据 Agent 解决问题所花费的排查轮数 (current_round vs max_rounds) 计算效率得分 (权重 10%)。
"""

from evaluator.schema import DimensionScore, GroundTruth
from runtime.schema import BlackboardState


class EfficiencyEvaluator:
    """诊断轮数效率评估器。

    权重占比: 10%
    计算逻辑:
    - 扣分公式: round_penalty = (current_round - 1) / max_rounds
    - 原始得分: raw_score = max(0.0, 1.0 - round_penalty)
    - 轮数越少，效率得分越高。
    """

    WEIGHT = 0.10

    def evaluate(self, state: BlackboardState, gt: GroundTruth) -> DimensionScore:
        """评估 Agent 诊断花费的轮数效率。

        Args:
            state: 包含诊断轮数信息的黑板状态 BlackboardState。
            gt: 当前场景的基准真值 GroundTruth。

        Returns:
            诊断效率维度的得分对象 DimensionScore。
        """
        current_round = state.get("current_round", 1)
        max_rounds = max(1, state.get("max_rounds", 5))

        round_penalty = (current_round - 1) / max_rounds
        raw_score = max(0.0, 1.0 - round_penalty)
        weighted_score = raw_score * self.WEIGHT * 100.0

        return DimensionScore(
            dimension="efficiency",
            raw_score=raw_score,
            weight=self.WEIGHT,
            weighted_score=weighted_score,
            details={
                "current_round": current_round,
                "max_rounds": max_rounds,
                "round_penalty": round_penalty,
            },
        )
