from typing import Any

from runtime.schema import BlackboardState


class MockLLMClient:
    """按轮次返回确定性并发与定向 dispatch 决议的 Mock LLM。"""

    def invoke(self, state: BlackboardState) -> dict[str, Any]:
        curr_round = state.get("current_round", 1)
        suspects = state.get("suspect_entities", ["order-service"])
        if curr_round == 1:
            return {
                "next_steps": [
                    "MetricsNode",
                    "LogsNode",
                    "TraceNode",
                    "KnowledgeNode",
                ],
                "suspect_entities": suspects,
            }
        elif curr_round == 2:
            return {
                "next_steps": ["LogsNode"],
                "suspect_entities": suspects,
            }
        else:
            return {
                "next_steps": ["Synthesizer"],
                "suspect_entities": suspects,
            }
