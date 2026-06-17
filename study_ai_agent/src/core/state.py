"""LangGraph 共享 state。

:class:`AgentState` 是外层 LangGraph 节点间传递的 **唯一** state 对象。
它承载：

* ``messages``           - 规范的 LangChain 聊天记录（流式发给 AG-UI 前端）
* ``plan`` / ``review``  - PERA 策略的 plan、review 节点填入的类型化侧信道
                           （Pydantic 模型）
* ``critique`` / ``current_draft`` / ``reflection_iterations``
                         - Reflection 策略的侧信道
* ``citations``          - research 骨架专属：execute 引用的来源（可选，可空）
* ``code_changes``       - coding 骨架专属：execute 产出的文件编辑（可选，可空）
* ``final_answer``       - act 节点的最终输出，暴露给 AG-UI

所有字段都是 ``total=False``，每个节点只写自己负责的 key；图的 reducer
（``add_messages``）负责合并。
"""

# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Annotated, Optional

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from src.core.schemas import Citation, CodeChange, Critique, Plan, Review


class AgentState(TypedDict, total=False):
    """外层 LangGraph（按 skill 参数化）共享的 state。"""

    # ---- 通用（每个智能体都会写这些） ----
    messages: Annotated[list[BaseMessage], add_messages]
    final_answer: Optional[str]

    # ---- PERA 策略的侧信道 ----
    plan: Optional[Plan]
    review: Optional[Review]

    # ---- Reflection 策略的侧信道 ----
    critique: Optional[Critique]
    current_draft: Optional[str]
    reflection_iterations: int

    # ---- 智能体专属的侧信道（可选） ----
    # research 智能体填充 ``citations``。
    citations: list[Citation]
    # coding 智能体填充 ``code_changes``。
    code_changes: list[CodeChange]


__all__ = ["AgentState"]
