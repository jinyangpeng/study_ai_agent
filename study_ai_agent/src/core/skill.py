"""SkillModule - 智能体 / 技能的插件契约。

一个 *skill* 是一组自包含的行为，由共享的 Plan-Execute-Review-Act 核心图
（plan -> execute -> review -> act）驱动。核心图不关心任何具体智能体；
它只消费 skill 通过本 Protocol 暴露的内容。

为什么用 Protocol 而不是 ABC？
* 这是表达"只要有这些属性就 OK"的 Pythonic 方式。
* skill 可以是普通类、dataclass，甚至通过 ``@runtime_checkable`` 校验的
  实例，没有继承税。
* ``id`` / ``name`` / ``description`` 三元组就是面向 AG-UI 的 manifest，
  通过 ``GET /skeletons`` 端点暴露给前端渲染选择器。

HITL 策略是 per-skill 的，不是全局的：coding 智能体在 ``write_file`` /
``shell_exec`` 之前需要人工审批，research 智能体什么都不要审（它没有副作用）。
"""
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool


@runtime_checkable
class SkillModule(Protocol):
    """skill（也叫 skeleton / mode）的插件契约。

    :mod:`src.core.graph` 中的核心 LangGraph 在编译时调用这些 accessor，
    把正确的工具、提示词、HITL 规则注入到各个节点。
    """

    # ---- AG-UI manifest ----
    @property
    def id(self) -> str:
        """稳定标识（如 ``"coding"``）。用在 URL 和 AG-UI 前端发来的
        ``forwarded_props.skill`` 中。"""
        ...

    @property
    def name(self) -> str:
        """人类可读的名字，显示在 AG-UI 选择器中（如 ``"编程智能体"``）。"""
        ...

    @property
    def description(self) -> str:
        """一句话说明这个 skill 擅长什么。"""
        ...

    # ---- Plan-Execute-Review-Act 各节点的 prompt ----
    @property
    def plan_prompt(self) -> str:
        """plan 子 agent 的 system prompt（输出 :class:`Plan`）。"""
        ...

    @property
    def execute_prompt(self) -> str:
        """execute 子 agent 的 system prompt（带工具集）。"""
        ...

    @property
    def review_prompt(self) -> str:
        """review 子 agent 的 system prompt（输出 :class:`Review`）。"""
        ...

    # ---- 工具集 ----
    @property
    def tools(self) -> list["BaseTool"]:
        """execute 子 agent 可用的工具。

        plan 和 review 子 agent 永远以 ``tools=[]`` 运行；
        只有 execute 会拿到 skill 的工具集。
        """
        ...

    # ---- 可选扩展 ----
    @property
    def hitl_rules(self) -> dict[str, dict[str, list[str]]]:
        """HITL interrupt 策略。

        形如 ``tool-name -> {"allowed_decisions": [...]}``，
        与 LangChain 1.x 的 :class:`HumanInTheLoopMiddleware` 的
        ``interrupt_on`` 参数形状一致。空字典表示"没有任何工具需要人工审批"
        （research 智能体就是这种情况）。

        示例::

            {
                "write_file": {"allowed_decisions": ["approve", "edit", "reject"]},
                "shell_exec": {"allowed_decisions": ["approve", "reject"]},
            }
        """
        ...

    def transform_final_answer(self, raw: str) -> str:
        """在 act 节点的输出发给前端之前做后处理。默认是恒等。
        可以用这个给最终答案加 skill 专属的页脚、格式化引用、去掉 diff 块。"""
        ...


__all__ = ["SkillModule"]
