from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from runtime.agents.knowledge_agent import knowledge_node
from runtime.agents.logs_agent import logs_node
from runtime.agents.metrics_agent import metrics_node
from runtime.agents.supervisor import supervisor_node
from runtime.agents.synthesizer import synthesizer_node
from runtime.agents.trace_agent import trace_node
from runtime.schema import BlackboardState


def route_supervisor(state: BlackboardState) -> list[str]:
    """根据 Supervisor 输出的 next_steps 进行动态扇出条件路由。"""
    steps = state.get("next_steps", [])
    status = state.get("status", "RUNNING")
    curr_round = state.get("current_round", 1)
    max_rounds = state.get("max_rounds", 5)

    if status == "COMPLETED" or curr_round > max_rounds or "Synthesizer" in steps:
        return ["Synthesizer"]
    return steps if steps else ["Synthesizer"]


def build_diagnosis_graph():
    """构建原生的 LangGraph StateGraph，接入 MemorySaver Checkpointer。"""
    builder = StateGraph(BlackboardState)

    # 注册节点
    builder.add_node("Supervisor", supervisor_node)
    builder.add_node("MetricsNode", metrics_node)
    builder.add_node("LogsNode", logs_node)
    builder.add_node("TraceNode", trace_node)
    builder.add_node("KnowledgeNode", knowledge_node)
    builder.add_node("Synthesizer", synthesizer_node)

    # 设入口为 Supervisor
    builder.set_entry_point("Supervisor")

    # 条件边：Supervisor 按 next_steps 并行扇出到各 Specialist Nodes
    builder.add_conditional_edges(
        "Supervisor",
        route_supervisor,
        {
            "MetricsNode": "MetricsNode",
            "LogsNode": "LogsNode",
            "TraceNode": "TraceNode",
            "KnowledgeNode": "KnowledgeNode",
            "Synthesizer": "Synthesizer",
        },
    )

    # Specialist Nodes 执完后汇合交回 Supervisor
    builder.add_edge("MetricsNode", "Supervisor")
    builder.add_edge("LogsNode", "Supervisor")
    builder.add_edge("TraceNode", "Supervisor")
    builder.add_edge("KnowledgeNode", "Supervisor")

    # Synthesizer 诊断结束
    builder.add_edge("Synthesizer", END)

    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)


def run_diagnosis_workflow(
    alert_dict: dict[str, Any], thread_id: str = "incident-001"
) -> BlackboardState:
    """运行全流程微服务故障诊断。"""
    graph = build_diagnosis_graph()
    initial_state: BlackboardState = {
        "messages": [],
        "incident_alert": alert_dict,
        "suspect_entities": [alert_dict.get("service", "unknown-service")],
        "evidences": [],
        "matched_runbooks": [],
        "current_round": 1,
        "max_rounds": 5,
        "next_steps": [],
        "diagnosis_report": None,
        "status": "RUNNING",
    }
    config = {"configurable": {"thread_id": thread_id}}
    final_state = graph.invoke(initial_state, config=config)
    return final_state
