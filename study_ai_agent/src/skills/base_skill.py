"""SkillModule 的便利基类。

不是 Protocol 的强制要求 —— 智能体可以直接实现
:mod:`src.core.skill` 里的 :class:`SkillModule`，不需要继承任何东西。
本类只是把"4 个 prompt 全都默认 None，让调用方挑着覆盖"这种最常见的
写法做成现成 API。
"""
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool


class BaseSkill:
    """智能体的默认实现 —— 4 个 prompt 都是 ``None``，调用方按需覆盖。"""

    # ---- AG-UI manifest ----
    id: str = ""
    name: str = ""
    description: str = ""

    # ---- 每个节点的 prompt ----
    planner_prompt: str = ""
    executor_prompt: str = ""
    reviewer_prompt: str = ""

    # ---- 前端欢迎区的快捷提示卡（按当前 skill 个性化） ----
    # 列表里每条 = 一张卡。空 list = 前端用通用默认。
    quick_prompts: list[dict[str, str]] = []

    @property
    def tools(self) -> list["BaseTool"]:
        """executor 可用的工具集。

        默认空。子 skill 用 :class:`property` 装饰来注入真实工具。
        """
        return []

    @property
    def hitl_rules(self) -> dict[str, dict[str, list[str]]]:
        """HITL interrupt 策略，默认空（无任何工具需要审批）。"""
        return {}

    def transform_final_answer(self, raw: str) -> str:
        """默认是恒等 —— 子 skill 可选重写。"""
        return raw


__all__ = ["BaseSkill"]
