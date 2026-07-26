"""Agent 节点模块。

设计原则：异构多 Agent（异质 Agent）架构。
- Supervisor、Synthesizer 为 LLM Agent，具备推理决策能力。
- LogsNode、MetricsNode、TraceNode、KnowledgeNode 目前为轻量工具执行节点，
  直接绑定 MCP 工具调用，无需 LLM 提示词。后续如需深度探索式分析
  （如动态决定查询参数、多轮上下文推理），可在此目录下扩展为完整 LLM Agent。
"""
