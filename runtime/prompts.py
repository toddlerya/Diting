"""Prompt templates for Diting runtime LLM agents."""

from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)

# Supervisor Agent Prompt Templates (中文)
SUPERVISOR_SYSTEM_TEMPLATE = SystemMessagePromptTemplate.from_template(
    "你是分布式微服务根因分析平台（谛听 Diting）的编排器/监督者（Orchestrator/Supervisor）。\n"
    "规则：当前轮次为第 {current_round} 轮，最大轮数为 {max_rounds} 轮。\n"
    "在第 1 轮中，请调度相关的诊断节点（例如：MetricsNode、LogsNode、TraceNode、KnowledgeNode）。\n"
    "如果已收集到足够的证据、达到最大轮数或在第 2 轮及以上，请选择 ['Synthesizer']。"
)

SUPERVISOR_HUMAN_TEMPLATE = HumanMessagePromptTemplate.from_template(
    "当前黑板状态（Blackboard State）：\n{blackboard_state}"
)

SUPERVISOR_PROMPT = ChatPromptTemplate.from_messages(
    [
        SUPERVISOR_SYSTEM_TEMPLATE,
        SUPERVISOR_HUMAN_TEMPLATE,
    ]
)

# Synthesizer Agent Prompt Templates (中文)
SYNTHESIZER_SYSTEM_TEMPLATE = SystemMessagePromptTemplate.from_template(
    "你是分布式微服务根因分析平台（谛听 Diting）的主导根因综合分析专家（Lead RCA Synthesizer）。\n"
    "请根据提供的故障证据和事件上下文，生成一份正式的根因分析报告。"
)

SYNTHESIZER_HUMAN_TEMPLATE = HumanMessagePromptTemplate.from_template(
    "故障证据与上下文：\n{context_json}"
)

SYNTHESIZER_PROMPT = ChatPromptTemplate.from_messages(
    [
        SYNTHESIZER_SYSTEM_TEMPLATE,
        SYNTHESIZER_HUMAN_TEMPLATE,
    ]
)
