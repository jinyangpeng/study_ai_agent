"""SkillModule 的便利基类。

不是 Protocol 的强制要求 —— 智能体可以直接实现
:mod:`src.core.skill` 里的 :class:`SkillModule`，不需要继承任何东西。
本类只是把"3 个 prompt 全都默认 None，让调用方挑着覆盖"这种最常见的
写法做成现成 API。
"""

# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool


class BaseSkill:
    """智能体的默认实现 —— 3 个 prompt 都是 ``None``，调用方按需覆盖。

    选策略
    ------
    :attr:`strategy` 默认 ``"p_e_r_a"``；子类可覆盖成 ``"react"`` /
    ``"reflection"`` 等已注册策略。覆盖时**必须**拼对（拼错会立刻
    :class:`ValueError`，错误信息列出可用策略名）。
    """

    # ---- AG-UI manifest ----
    id: str = ""
    name: str = ""
    description: str = ""

    # ---- 推理策略 ----
    # 默认 PERA；子类按需 override。覆盖值在 __init_subclass__ 里被 validate。
    strategy: str = "p_e_r_a"

    # ---- Plan-Execute-Review-Act 每个节点的 prompt ----
    plan_prompt: str = ""
    execute_prompt: str = ""
    review_prompt: str = ""

    # ---- ReAct 策略的 prompt ----
    react_prompt: str = ""

    # ---- Reflection 策略的 prompt ----
    reflection_generate_prompt: str = ""
    reflection_critique_prompt: str = ""
    reflection_refine_prompt: str = ""
    max_reflection_iterations: int = 3

    # ---- 前端欢迎区的快捷提示卡（按当前 skill 个性化） ----
    # 列表里每条 = 一张卡。空 list = 前端用通用默认。
    quick_prompts: list[dict[str, str]] = []

    @property
    def tools(self) -> list["BaseTool"]:
        """execute 节点可用的工具集。

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

    def __init_subclass__(cls, **kwargs) -> None:
        """子类一 import 就校验 ``strategy`` 字段已注册。

        Fail-fast：拼错策略名（典型错误：``"react"`` 写成 ``"React"`` /
        ``"re_act"``）会在**进程启动期**抛 :class:`ValueError`，错误信息
        列出所有可用策略名。不会拖到第一次请求才炸，运维 / 排障成本最低。
        """
        super().__init_subclass__(**kwargs)
        from src.core.strategies import validate as _validate_strategy

        name = getattr(cls, "strategy", "") or "p_e_r_a"
        # 覆盖回类属性，让 IDE / 调用方读到的就是规范化过的
        cls.strategy = name
        _validate_strategy(name)


__all__ = ["BaseSkill"]
