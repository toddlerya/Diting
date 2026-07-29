"""根因定位准度评估器 (Root Cause Accuracy Evaluator)。

评估 Agent 提交的诊断报告 (DiagnosisReport) 中根因实体与故障类型的准确性，
结合 Agent 的置信度计算根因定位维度的得分 (权重 40%)。
"""

from evaluator.schema import DimensionScore, GroundTruth
from runtime.schema import DiagnosisReport


class RootCauseEvaluator:
    """根因准确率评估器。

    权重占比: 40%
    计算逻辑:
    - 根因实体匹配 (60% 子权重): 完全一致得 1.0，包含/子串匹配得 0.6。
    - 故障类型匹配 (40% 子权重): 词拆分或子串匹配一致得 1.0。
    - 最终得分结合 Agent 的诊断置信度 (confidence) 进行加权。
    """

    WEIGHT = 0.40

    def evaluate(self, report: DiagnosisReport | None, gt: GroundTruth) -> DimensionScore:
        """评估根因定位准确率。

        Args:
            report: Agent Runtime 提交的最终诊断报告 DiagnosisReport (若无则得 0 分)。
            gt: 当前场景的基准真值 GroundTruth。

        Returns:
            根因定位维度的得分对象 DimensionScore。
        """
        if not report:
            return DimensionScore(
                dimension="root_cause",
                raw_score=0.0,
                weight=self.WEIGHT,
                weighted_score=0.0,
                details={"reason": "No diagnosis report provided"},
            )

        # 1. 实体匹配度计算 (60% 子权重)
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

        # 2. 故障类型匹配度计算 (40% 子权重)
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

        # 3. 结合置信度加权得出原始得分
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
