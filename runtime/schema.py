import operator
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field


class Evidence(BaseModel):
    id: str
    source: Literal["metric", "log", "trace", "runbook"]
    entity_id: str
    timestamp: str  # ISO 8601 UTC string (+00:00)
    summary: str
    details: dict = Field(default_factory=dict)
    relevance_score: float = 1.0  # fallback 证据置 0.0，避免被当作真实事实


class DiagnosisReport(BaseModel):
    root_cause_entity: str
    failure_type: str  # e.g., "CPU_BURST", "MEMORY_LEAK", "NETWORK_LATENCY"
    confidence: float  # 0.0 - 1.0
    evidence_ids: list[str]
    summary: str
    recommended_actions: list[str] = Field(default_factory=list)


ValidNodeName = Literal["MetricsNode", "LogsNode", "TraceNode", "KnowledgeNode", "Synthesizer"]


class SupervisorDecision(BaseModel):
    next_steps: list[ValidNodeName] = Field(
        description="List of exact node names to dispatch. MUST be selected from: 'MetricsNode', 'LogsNode', 'TraceNode', 'KnowledgeNode', 'Synthesizer'."
    )
    suspect_entities: list[str] = Field(
        default_factory=list,
        description="List of suspect entity IDs identified during investigation.",
    )
    reasoning: str = Field(
        default="",
        description="Brief rationale for the routing decision.",
    )


class BlackboardState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]
    incident_alert: dict
    suspect_entities: list[str]
    evidences: Annotated[list[Evidence], operator.add]
    matched_runbooks: Annotated[list[dict], operator.add]
    current_round: int
    max_rounds: int
    next_steps: list[str]  # 并发派发节点列表，如 ["MetricsNode", "LogsNode"]
    diagnosis_report: DiagnosisReport | None
    status: Literal["RUNNING", "COMPLETED", "FAILED"]
