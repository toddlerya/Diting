from runtime.prompts import SUPERVISOR_PROMPT, SYNTHESIZER_PROMPT


def test_supervisor_prompt_formatting():
    messages = SUPERVISOR_PROMPT.format_messages(
        current_round=1,
        max_rounds=5,
        blackboard_state="{}",
    )
    assert len(messages) == 2
    assert "谛听 Diting" in messages[0].content
    assert "当前轮次为第 1 轮" in messages[0].content
    assert "当前黑板状态（Blackboard State）：" in messages[1].content


def test_synthesizer_prompt_formatting():
    messages = SYNTHESIZER_PROMPT.format_messages(
        context_json="{}",
    )
    assert len(messages) == 2
    assert "根因分析报告" in messages[0].content
    assert "故障证据与上下文：" in messages[1].content
