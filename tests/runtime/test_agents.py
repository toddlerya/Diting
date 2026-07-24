from runtime.agents.knowledge_agent import knowledge_node
from runtime.agents.logs_agent import logs_node
from runtime.agents.metrics_agent import metrics_node
from runtime.agents.supervisor import supervisor_node
from runtime.agents.synthesizer import synthesizer_node
from runtime.agents.trace_agent import trace_node
from runtime.mock_llm import MockLLMClient
from runtime.schema import BlackboardState


def test_mock_llm_multi_round_decisions():
    client = MockLLMClient()

    # Round 1 -> Parallel dispatch
    state1: BlackboardState = {
        "messages": [],
        "incident_alert": {"service": "order-service"},
        "suspect_entities": ["order-service"],
        "evidences": [],
        "matched_runbooks": [],
        "current_round": 1,
        "max_rounds": 5,
        "next_steps": [],
        "diagnosis_report": None,
        "status": "RUNNING",
    }
    resp1 = client.invoke(state1)
    assert set(resp1["next_steps"]) == {"MetricsNode", "LogsNode", "TraceNode", "KnowledgeNode"}


def test_supervisor_node():
    state: BlackboardState = {
        "messages": [],
        "incident_alert": {"service": "order-service"},
        "suspect_entities": ["order-service"],
        "evidences": [],
        "matched_runbooks": [],
        "current_round": 1,
        "max_rounds": 5,
        "next_steps": [],
        "diagnosis_report": None,
        "status": "RUNNING",
    }
    update = supervisor_node(state)
    assert "next_steps" in update
    assert update["current_round"] == 2


def test_metrics_node_wrapper():
    state: BlackboardState = {
        "messages": [],
        "incident_alert": {},
        "suspect_entities": ["order-service"],
        "evidences": [],
        "matched_runbooks": [],
        "current_round": 1,
        "max_rounds": 5,
        "next_steps": ["MetricsNode"],
        "diagnosis_report": None,
        "status": "RUNNING",
    }
    update = metrics_node(state)
    assert "evidences" in update
    assert "messages" in update
    assert len(update["evidences"]) == 1
    assert update["evidences"][0].source == "metric"


def test_logs_node_wrapper():
    state: BlackboardState = {
        "messages": [],
        "incident_alert": {},
        "suspect_entities": ["order-service"],
        "evidences": [],
        "matched_runbooks": [],
        "current_round": 1,
        "max_rounds": 5,
        "next_steps": ["LogsNode"],
        "diagnosis_report": None,
        "status": "RUNNING",
    }
    update = logs_node(state)
    assert "evidences" in update
    assert update["evidences"][0].source == "log"


def test_trace_node_wrapper():
    state: BlackboardState = {
        "messages": [],
        "incident_alert": {},
        "suspect_entities": ["order-service"],
        "evidences": [],
        "matched_runbooks": [],
        "current_round": 1,
        "max_rounds": 5,
        "next_steps": ["TraceNode"],
        "diagnosis_report": None,
        "status": "RUNNING",
    }
    update = trace_node(state)
    assert "evidences" in update
    assert update["evidences"][0].source == "trace"


def test_knowledge_node_wrapper():
    state: BlackboardState = {
        "messages": [],
        "incident_alert": {},
        "suspect_entities": ["order-service"],
        "evidences": [],
        "matched_runbooks": [],
        "current_round": 1,
        "max_rounds": 5,
        "next_steps": ["KnowledgeNode"],
        "diagnosis_report": None,
        "status": "RUNNING",
    }
    update = knowledge_node(state)
    assert "evidences" in update
    assert update["evidences"][0].source == "runbook"


def test_synthesizer_node_wrapper():
    state: BlackboardState = {
        "messages": [],
        "incident_alert": {"service": "order-service"},
        "suspect_entities": ["order-service"],
        "evidences": [],
        "matched_runbooks": [],
        "current_round": 2,
        "max_rounds": 5,
        "next_steps": ["Synthesizer"],
        "diagnosis_report": None,
        "status": "RUNNING",
    }
    update = synthesizer_node(state)
    assert update["status"] == "COMPLETED"
    assert update["diagnosis_report"].root_cause_entity == "order-service"
