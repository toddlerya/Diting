from typing import Any

from runtime.llm import invoke_supervisor_llm
from runtime.mock_llm import MockLLMClient
from runtime.schema import BlackboardState


def supervisor_node(state: BlackboardState) -> dict[str, Any]:
    decision = invoke_supervisor_llm(state)
    if not decision:
        client = MockLLMClient()
        decision = client.invoke(state)

    update: dict[str, Any] = {
        "next_steps": decision.get("next_steps", ["Synthesizer"]),
        "current_round": state.get("current_round", 1) + 1,
    }
    if "suspect_entities" in decision:
        update["suspect_entities"] = decision["suspect_entities"]
    return update
