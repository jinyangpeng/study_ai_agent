# -*- coding: utf-8 -*-
"""消息裁剪 + 工具超时辅助（#25 / #26）。

#25 消息裁剪
------------
长对话历史会让 LLM context 爆炸（token 超限、成本失控、响应变慢）。
:func:`trim_messages` 在每次调 agent 前裁剪消息：

* 保留所有 ``SystemMessage``（system prompt 不能丢）
* 保留最近 ``max_messages`` 条非 system 消息
* 如果裁剪掉了带 ``tool_calls`` 的 AIMessage，对应的 ToolMessage 也会被
  清理（避免孤儿 ToolMessage 导致 LLM 报错）

#26 工具超时
------------
:func:`with_tool_timeout` 给单个工具的 ``_arun`` / ``_run`` 加 ``asyncio.wait_for``
超时保护。工具卡住时抛 :class:`ToolTimeoutError`，被 :mod:`safe_tool` 的
``make_safe`` 接住转成结构化 JSON，不会让 graph panic。
"""
from __future__ import annotations

import asyncio
import logging

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# #25 消息裁剪
# ---------------------------------------------------------------------------
def trim_messages(
    messages: list[BaseMessage],
    max_messages: int,
) -> list[BaseMessage]:
    """裁剪消息列表，保留 system + 最近 ``max_messages`` 条非 system 消息。

    :param messages: 原始消息列表
    :param max_messages: 保留的非 system 消息数上限。``<=0`` 时直接返回原列表（关闭裁剪）
    :returns: 裁剪后的消息列表

    裁剪规则：
    1. 所有 ``SystemMessage`` 保留（system prompt 不能丢）
    2. 非 system 消息只保留最近 ``max_messages`` 条
    3. 如果裁剪导致出现孤儿 ``ToolMessage``（对应的 ``AIMessage.tool_calls``
       被裁掉了），把这些孤儿也清掉
    """
    if max_messages <= 0 or len(messages) <= max_messages:
        return list(messages)

    # 分离 system / 非 system
    system_msgs: list[BaseMessage] = []
    other_msgs: list[BaseMessage] = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            system_msgs.append(msg)
        else:
            other_msgs.append(msg)

    # 非 system 只保留最后 N 条
    if len(other_msgs) <= max_messages:
        return list(messages)

    kept_other = other_msgs[-max_messages:]
    trimmed = system_msgs + kept_other

    # 清理孤儿 ToolMessage：如果 kept_other 开头有 ToolMessage 但对应的
    # AIMessage（带 tool_calls）被裁掉了，LLM 会报 "ToolMessage without
    # preceding AIMessage with tool_calls" 错误。
    trimmed = _drop_orphan_tool_messages(trimmed)

    dropped = len(messages) - len(trimmed)
    if dropped > 0:
        logger.info(
            "消息裁剪: %d → %d（保留 system=%d + 最近 %d 条，清理孤儿 %d 条）",
            len(messages), len(trimmed), len(system_msgs), max_messages,
            dropped - (len(other_msgs) - max_messages) if len(other_msgs) > max_messages else 0,
        )
    return trimmed


def _drop_orphan_tool_messages(messages: list[BaseMessage]) -> list[BaseMessage]:
    """清理孤儿 ToolMessage（对应的 AIMessage.tool_calls 不在列表里）。

    孤儿 ToolMessage 会让 LLM 报错（"ToolMessage without preceding AIMessage
    with tool_calls"）。检测逻辑：遍历消息，维护一个 ``seen_tool_call_ids``
    集合，ToolMessage 的 ``tool_call_id`` 不在集合里就是孤儿。
    """
    seen_tool_call_ids: set[str] = set()
    for msg in messages:
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            for tc in msg.tool_calls:
                tc_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                if tc_id:
                    seen_tool_call_ids.add(tc_id)

    if not seen_tool_call_ids:
        # 没有 tool_calls → 所有 ToolMessage 都是孤儿
        has_orphan = any(isinstance(m, ToolMessage) for m in messages)
        if not has_orphan:
            return messages
        return [m for m in messages if not isinstance(m, ToolMessage)]

    return [
        m for m in messages
        if not (isinstance(m, ToolMessage) and m.tool_call_id not in seen_tool_call_ids)
    ]


# ---------------------------------------------------------------------------
# #26 工具超时
# ---------------------------------------------------------------------------
class ToolTimeoutError(TimeoutError):
    """工具调用超时异常。"""


def with_tool_timeout(tool: BaseTool, timeout_seconds: float) -> BaseTool:
    """给工具的 ``_arun`` / ``_run`` 加超时保护。

    :param tool: 原始 LangChain 工具
    :param timeout_seconds: 超时秒数。``<=0`` 时直接返回原工具（关闭超时）
    :returns: 包装后的工具（同一实例，方法被 monkey-patch）

    实现方式：monkey-patch 工具的 ``_arun`` / ``_run``，在外面套一层
    ``asyncio.wait_for`` / ``asyncio.to_thread`` + ``asyncio.wait_for``。
    超时时抛 :class:`ToolTimeoutError`，被 :func:`make_safe` 接住转成
    结构化 JSON。

    注意：这里直接修改原工具实例（不创建新类），因为 LangChain 的
    ``create_agent`` 会检查 ``isinstance(tool, BaseTool)``，创建子类
    可能导致类型检查失败。
    """
    if timeout_seconds <= 0:
        return tool

    original_arun = tool._arun
    original_run = tool._run

    async def _timed_arun(*args, **kwargs):
        try:
            return await asyncio.wait_for(
                original_arun(*args, **kwargs),
                timeout=timeout_seconds,
            )
        except TimeoutError as exc:
            raise ToolTimeoutError(
                f"Tool '{tool.name}' timed out after {timeout_seconds}s"
            ) from exc

    async def _timed_run(*args, **kwargs):
        # 同步 _run 用 to_thread 包一层再 wait_for
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(original_run, *args, **kwargs),
                timeout=timeout_seconds,
            )
        except TimeoutError as exc:
            raise ToolTimeoutError(
                f"Tool '{tool.name}' timed out after {timeout_seconds}s"
            ) from exc

    tool._arun = _timed_arun  # type: ignore[method-assign]
    tool._run = _timed_run  # type: ignore[method-assign]
    return tool


def wrap_tools_with_timeout(
    tools: list[BaseTool],
    timeout_seconds: float,
) -> list[BaseTool]:
    """批量给工具列表加超时保护。

    :param tools: 原始工具列表
    :param timeout_seconds: 超时秒数。``<=0`` 时直接返回原列表
    :returns: 包装后的工具列表（同一批实例，方法被 patch）
    """
    if timeout_seconds <= 0:
        return tools
    return [with_tool_timeout(t, timeout_seconds) for t in tools]


__all__ = [
    "ToolTimeoutError",
    "trim_messages",
    "with_tool_timeout",
    "wrap_tools_with_timeout",
]
