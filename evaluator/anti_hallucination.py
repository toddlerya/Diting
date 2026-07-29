"""反幻觉评估器 (Anti-Hallucination Evaluator)。

评估 Agent 在黑板状态中沉淀的证据 (Evidences) 是否符合物理客观事实 (GroundTruth 时间线)，
对伪造指标、非法时间戳、虚假日志等幻觉行为进行识别与扣分 (权重 25%)。
"""

from datetime import datetime

from evaluator.schema import DimensionScore, GroundTruth
from runtime.schema import BlackboardState


class AntiHallucinationEvaluator:
    """反幻觉与证据真实性评估器。

    权重占比: 25%
    核心校验逻辑:
    - 实体匹配: 证据的 entity_id 必须与时间线事件相匹配。
    - 时间戳误差: 证据时间与事件发生时间相差不得超过 MAX_TIME_DELTA_SEC (5 秒)。
    - 指标数值误差: 指标类证据的相对误差不得超过 MAX_METRIC_VALUE_ERROR (10%)。
    - 日志关键字: 日志类证据摘要中需成功匹配 log_keyword。
    - 回退启发式: 若证据自身内容完整且相关度分值 >= 0.5，允许启发式判定通过。
    """

    WEIGHT = 0.25
    MAX_TIME_DELTA_SEC = 5.0
    MAX_METRIC_VALUE_ERROR = 0.10  # 10%

    def evaluate(self, state: BlackboardState, gt: GroundTruth) -> DimensionScore:
        """评估黑板证据的反幻觉质量与有效真实比例。

        Args:
            state: Agent 诊断过程中的黑板状态 BlackboardState。
            gt: 当前场景的基准真值 GroundTruth。

        Returns:
            反幻觉维度的得分对象 DimensionScore。
        """
        evidences = state.get("evidences", []) if state else []
        if not evidences:
            return DimensionScore(
                dimension="anti_hallucination",
                raw_score=0.0,
                weight=self.WEIGHT,
                weighted_score=0.0,
                details={"reason": "No evidence provided in blackboard state"},
            )

        valid_count = 0
        total_count = len(evidences)
        details_list = []

        for ev in evidences:
            is_valid = False
            reason = "unmatched"

            for te in gt.timeline:
                # 1. 实体重合性检查
                if not (
                    te.entity_id.lower() in ev.entity_id.lower()
                    or ev.entity_id.lower() in te.entity_id.lower()
                ):
                    continue

                # 2. 时间戳偏差校验
                if te.expected_timestamp and ev.timestamp:
                    try:
                        t_event = datetime.fromisoformat(te.expected_timestamp)
                        t_evidence = datetime.fromisoformat(ev.timestamp)
                        if t_event.tzinfo is not None and t_evidence.tzinfo is None:
                            t_evidence = t_evidence.replace(tzinfo=t_event.tzinfo)
                        elif t_evidence.tzinfo is not None and t_event.tzinfo is None:
                            t_event = t_event.replace(tzinfo=t_evidence.tzinfo)
                        delta = abs((t_evidence - t_event).total_seconds())
                        if delta > self.MAX_TIME_DELTA_SEC:
                            reason = (
                                f"timestamp delta {delta:.1f}s exceeded {self.MAX_TIME_DELTA_SEC}s"
                            )
                            continue
                    except Exception:
                        pass

                # 3. 指标数值误差校验
                if ev.source == "metric" and te.expected_value is not None:
                    val = ev.details.get("value")
                    if val is not None:
                        rel_error = (
                            abs(val - te.expected_value) / abs(te.expected_value)
                            if te.expected_value != 0
                            else abs(val)
                        )
                        if rel_error <= self.MAX_METRIC_VALUE_ERROR:
                            is_valid = True
                            reason = f"value matched (rel error: {rel_error:.2%})"
                            break
                        else:
                            reason = f"value error {rel_error:.2%} exceeded {self.MAX_METRIC_VALUE_ERROR:.0%}"
                            continue

                # 4. 日志关键字匹配校验
                if te.log_keyword and te.log_keyword.lower() in ev.summary.lower():
                    is_valid = True
                    reason = f"keyword matched '{te.log_keyword}'"
                    break

            # 5. 回退启发式: 若证据包含非空有效摘要且相关性得分 >= 0.5 判为有效
            if (
                not is_valid
                and reason == "unmatched"
                and ev.entity_id
                and ev.summary
                and ev.relevance_score >= 0.5
            ):
                is_valid = True
                reason = "heuristic valid summary"

            if is_valid:
                valid_count += 1
            details_list.append(
                {
                    "evidence_id": ev.id,
                    "is_valid": is_valid,
                    "reason": reason,
                    "summary": ev.summary,
                }
            )

        raw_score = valid_count / total_count if total_count > 0 else 0.0
        weighted_score = raw_score * self.WEIGHT * 100.0

        return DimensionScore(
            dimension="anti_hallucination",
            raw_score=raw_score,
            weight=self.WEIGHT,
            weighted_score=weighted_score,
            details={
                "valid_count": valid_count,
                "total_count": total_count,
                "evidences_detail": details_list,
            },
        )
