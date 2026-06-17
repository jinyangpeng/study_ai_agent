"""图构建器 - 通过策略工厂按 skill 编译 LangGraph。

策略（Plan-Execute-Review-Act / ReAct / Reflection）由
:mod:`src.core.strategies` 提供。这里只负责：

1. 默认从 :attr:`SkillModule.strategy` 挑策略
2. 用 ``model_factory`` 解析 chat model
3. 注入 ``checkpointer_factory.saver`` 并设置 ``recursion_limit``
4. 调 ``strategy.build_graph(skill, model, checkpointer)`` 拿编译结果

调用方可以显式传 ``strategy_name`` 覆盖（主要用于测试 / 临时切换），
不传时走 skill 自己声明的策略。
"""

# -*- coding: utf-8 -*-
from __future__ import annotations

from langgraph.graph.state import CompiledStateGraph

from src.config.settings import get_settings
from src.core.checkpointer import checkpointer_factory
from src.core.model_factory import model_factory
from src.core.skill import SkillModule
from src.core.strategies import get as get_strategy

__all__ = ["build_graph"]


def build_graph(
    skill: SkillModule,
    strategy_name: str | None = None,
) -> CompiledStateGraph:
    """为给定 skill + 策略编译 LangGraph。

    Parameters
    ----------
    skill
        当前 skill 模块。其 :attr:`~SkillModule.strategy` 字段决定默认
        使用哪个策略（已由 :class:`BaseSkill.__init_subclass__` 在 import
        时校验过一定合法）。
    strategy_name
        显式覆盖：不传（或 ``None``/空串）时用 ``skill.strategy``。传入值
        仍会经过 :func:`src.core.strategies.get` 的运行时校验（拼错会抛
        :class:`ValueError`），用于测试 / 临时切换。
    """
    name = strategy_name or skill.strategy
    model, _provider_name = model_factory.create_model()
    strategy = get_strategy(name)
    s = get_settings()
    graph = strategy.build_graph(
        skill=skill,
        model=model,
        checkpointer=checkpointer_factory.saver,
    )
    # recursion_limit 控制 PERA / Reflection 这类有循环边的图最多走多少步。
    # LangGraph 默认 25，对于工具频繁失败、LLM 多次重试 plan→execute→review
    # 的场景会过早撞顶（例如 DDG 一直 timeout，LLM 反复想"再搜一次试试"）。
    # 75 大约够 PERA 走 5-6 轮 revise + Reflection 5 轮 refine + buffer。
    # 想再保守可以通过环境变量 ``LANGGRAPH_RECURSION_LIMIT`` 覆盖。
    return graph.with_config({"recursion_limit": s.LANGGRAPH_RECURSION_LIMIT})
