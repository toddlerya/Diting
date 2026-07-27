from datetime import datetime

from evaluator.schema import DimensionScore, GroundTruth
from runtime.schema import BlackboardState


class AntiHallucinationEvaluator:
    WEIGHT = 0.25
    MAX_TIME_DELTA_SEC = 5.0
    MAX_METRIC_VALUE_ERROR = 0.10  # 10%

    def evaluate(self, state: BlackboardState, gt: GroundTruth) -> DimensionScore:
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
                # 1. Check entity match
                if not (
                    te.entity_id.lower() in ev.entity_id.lower()
                    or ev.entity_id.lower() in te.entity_id.lower()
                ):
                    continue

                # 2. Timestamp delta check if timestamps present
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

                # 3. Metric Value Error check
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

                # 4. Log Keyword check
                if te.log_keyword and te.log_keyword.lower() in ev.summary.lower():
                    is_valid = True
                    reason = f"keyword matched '{te.log_keyword}'"
                    break

            # Fallback heuristic: If evidence contains non-empty valid summary and entity_id
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
