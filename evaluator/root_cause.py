from evaluator.schema import DimensionScore, GroundTruth
from runtime.schema import DiagnosisReport


class RootCauseEvaluator:
    WEIGHT = 0.40

    def evaluate(self, report: DiagnosisReport | None, gt: GroundTruth) -> DimensionScore:
        if not report:
            return DimensionScore(
                dimension="root_cause",
                raw_score=0.0,
                weight=self.WEIGHT,
                weighted_score=0.0,
                details={"reason": "No diagnosis report provided"},
            )

        # 1. Entity Match (60% sub-weight)
        entity_score = 0.0
        if report.root_cause_entity == gt.root_cause_entity:
            entity_score = 1.0
        elif (
            (
                gt.root_cause_service
                and gt.root_cause_service.lower() in report.root_cause_entity.lower()
            )
            or (
                gt.root_cause_service
                and report.root_cause_entity.lower() in gt.root_cause_service.lower()
            )
            or (
                gt.root_cause_entity
                and report.root_cause_entity.lower() in gt.root_cause_entity.lower()
            )
        ):
            entity_score = 0.6

        # 2. Failure Type Match (40% sub-weight)
        type_score = 0.0
        r_type = report.failure_type.lower().replace("_", "")
        gt_type = gt.failure_type.lower().replace("_", "")
        r_words = set(report.failure_type.lower().replace("-", "_").split("_")) - {""}
        gt_words = set(gt.failure_type.lower().replace("-", "_").split("_")) - {""}
        if r_type and (
            r_type in gt_type
            or gt_type in r_type
            or (r_words and r_words <= gt_words)
            or (gt_words and gt_words <= r_words)
        ):
            type_score = 1.0

        confidence = max(0.0, min(1.0, report.confidence))
        raw_score = (0.6 * entity_score + 0.4 * type_score) * confidence
        weighted_score = raw_score * self.WEIGHT * 100.0

        return DimensionScore(
            dimension="root_cause",
            raw_score=raw_score,
            weight=self.WEIGHT,
            weighted_score=weighted_score,
            details={
                "entity_score": entity_score,
                "type_score": type_score,
                "confidence": confidence,
                "predicted_entity": report.root_cause_entity,
                "actual_entity": gt.root_cause_entity,
                "predicted_type": report.failure_type,
                "actual_type": gt.failure_type,
            },
        )
