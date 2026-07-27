from evaluator.schema import DimensionScore, GroundTruth
from runtime.schema import BlackboardState


class EfficiencyEvaluator:
    WEIGHT = 0.10

    def evaluate(self, state: BlackboardState, gt: GroundTruth) -> DimensionScore:
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
