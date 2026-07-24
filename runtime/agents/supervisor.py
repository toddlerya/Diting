from typing import Any

from runtime.mock_llm import MockLLMClient
from runtime.schema import BlackboardState


def supervisor_node(state: BlackboardState) -> dict[str, Any]:
    client = MockLLMClient()
    decision = client.invoke(state)
    return {
        "next_steps": decision.get("next_steps", ["Synthesizer"]),
        "current_round": state.get("current_round", 1) + 1,
    }
