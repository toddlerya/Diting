from langchain_core.messages import AIMessage

from evaluator.schema import DimensionScore, GroundTruth
from runtime.schema import BlackboardState


class PathRecallEvaluator:
    WEIGHT = 0.25

    def evaluate(self, state: BlackboardState, gt: GroundTruth) -> DimensionScore:
        actual_tools = set()
        actual_services = set()

        for msg in state.get("messages", []):
            if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_name = (
                        tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                    )
                    if tool_name:
                        actual_tools.add(tool_name)

                    args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
                    if isinstance(args, dict):
                        if args.get("entity_id"):
                            actual_services.add(args["entity_id"])
                        if args.get("service"):
                            actual_services.add(args["service"])

        expected_tools = set(gt.expected_tools)
        expected_services = set(gt.expected_services)

        # Tool Recall & Precision
        if not expected_tools:
            tool_score = 1.0 if not actual_tools else 0.5
        else:
            tp_tools = len(actual_tools.intersection(expected_tools))
            tool_recall = tp_tools / len(expected_tools)
            tool_precision = tp_tools / len(actual_tools) if actual_tools else 0.0
            tool_score = (
                2 * tool_precision * tool_recall / (tool_precision + tool_recall)
                if (tool_precision + tool_recall) > 0
                else 0.0
            )

        # Service Recall & Precision
        if not expected_services:
            svc_score = 1.0 if not actual_services else 0.5
        else:
            tp_svc = len(actual_services.intersection(expected_services))
            svc_recall = tp_svc / len(expected_services)
            svc_precision = tp_svc / len(actual_services) if actual_services else 0.0
            svc_score = (
                2 * svc_precision * svc_recall / (svc_precision + svc_recall)
                if (svc_precision + svc_recall) > 0
                else 0.0
            )

        raw_score = 0.5 * tool_score + 0.5 * svc_score
        weighted_score = raw_score * self.WEIGHT * 100.0

        return DimensionScore(
            dimension="path_recall",
            raw_score=raw_score,
            weight=self.WEIGHT,
            weighted_score=weighted_score,
            details={
                "tool_score": tool_score,
                "service_score": svc_score,
                "actual_tools": sorted(actual_tools),
                "expected_tools": sorted(expected_tools),
                "actual_services": sorted(actual_services),
                "expected_services": sorted(expected_services),
            },
        )
