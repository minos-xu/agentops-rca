
from __future__ import annotations

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
    SystemMessage,
)

from langchain_core.messages.utils import (
    count_tokens_approximately,
)


class ContextBudgetError(ValueError):
    pass


# =============================================
# 1. 按用户轮次拆分 History
# =============================================

def split_user_turns(
    messages: list[BaseMessage],
) -> list[list[BaseMessage]]:

    turns = []

    for message in messages:

        if isinstance(message, HumanMessage):

            turns.append([message])

        elif turns:

            # Assistant 和 Tool 都属于
            # 最近一个 HumanMessage 开始的轮次
            turns[-1].append(message)

        else:

            raise ValueError(
                "History 必须从 HumanMessage 开始"
            )

    return turns


# =============================================
# 2. 验证工具调用与结果是否配对
# =============================================

def validate_tool_pairs(
    messages: list[BaseMessage],
) -> None:

    pending = set()

    for message in messages:

        if isinstance(message, AIMessage):

            for call in message.tool_calls:

                call_id = call["id"]

                if call_id in pending:
                    raise ValueError(
                        f"重复 Tool Call ID: {call_id}"
                    )

                pending.add(call_id)

        elif isinstance(message, ToolMessage):

            call_id = message.tool_call_id

            if call_id not in pending:
                raise ValueError(
                    f"孤立 ToolMessage: {call_id}"
                )

            pending.remove(call_id)

    if pending:

        raise ValueError(
            f"存在尚未返回的 Tool Call: {pending}"
        )


# =============================================
# 3. 组装选中的轮次
# =============================================

def flatten_turns(turns):

    return [
        message
        for turn in turns
        for message in turn
    ]


# =============================================
# 4. 根据轮次与 Token Budget 裁剪
# =============================================

def prepare_llm_context(
    messages: list[BaseMessage],
    system_prompt: str,
    tool_schemas: list[dict],
    max_turns: int = 3,
    max_input_tokens: int = 3500,
) -> list[BaseMessage]:

    if max_turns < 1 or max_input_tokens < 1:
        raise ValueError(
            "max_turns 和 max_input_tokens 必须大于 0"
        )

    turns = split_user_turns(messages)

    if not turns:
        raise ValueError("当前没有用户消息")

    system = SystemMessage(
        content=system_prompt
    )

    def build(selected_turns):

        return [
            system,
            *flatten_turns(selected_turns),
        ]

    def token_count(selected_turns):

        return count_tokens_approximately(
            build(selected_turns),
            tools=tool_schemas,
        )

    # 必须完整保留当前正在执行的用户轮次
    kept = [turns[-1]]

    if token_count(kept) > max_input_tokens:

        raise ContextBudgetError(
            "当前轮次加上 System Prompt 和工具"
            "定义已超过输入预算。"
            "请缩短请求或限制工具输出，"
            "不要截断 Tool Call 配对。"
        )

    # 从近到远尝试加入历史轮次
    for old_turn in reversed(turns[:-1]):

        if len(kept) >= max_turns:
            break

        candidate = [
            old_turn,
            *kept,
        ]

        if token_count(candidate) > max_input_tokens:
            break

        kept = candidate

    selected = build(kept)

    # 发送给 LLM 前检查消息结构
    validate_tool_pairs(selected)

    return selected
