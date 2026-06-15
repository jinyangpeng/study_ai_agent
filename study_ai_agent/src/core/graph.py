"""图构建器 - 通过策略工厂按 skill 编译 LangGraph。

策略（Plan-Execute-Review-Act / 未来的 ReAct / Reflection）由
:mod:`src.core.strategies` 提供。这里只负责：

1. 调用 :func:`src.core.strategies.get` 拿到当前策略实例
2. 用 ``model_factory`` 解析 chat model
3. 注入 ``checkpointer_factory.saver``
4. 调 ``strategy.build_graph(skill, model, checkpointer)`` 拿编译结果

如果想给所有 skill 切换策略，**只**改策略注册表 / 配置即可，
本文件不用动。
"""
# -*- coding: utf-8 -*-
from __future__ import annotations

from langgraph.graph.state import CompiledStateGraph

from src.core.checkpointer import checkpointer_factory
from src.core.model_factory import model_factory
from src.core.skill import SkillModule
from src.core.strategies import get as get_strategy

# 当前默认策略名。新策略加进来后可以通过 settings / skill.strategy 切换。
DEFAULT_STRATEGY = "p_e_r_a"


def build_graph(
    skill: SkillModule,
    strategy_name: str = DEFAULT_STRATEGY,
) -> CompiledStateGraph:
    """为给定 skill + 策略编译 LangGraph。

    Parameters
    ----------
    skill
        当前 skill 模块。
    strategy_name
        策略名（必须已经在 :mod:`src.core.strategies` 注册过）。
        默认 ``"p_e_r_a"``。所有 skill 共享一个 chat model + checkpointer。
    """
    model, _provider_name = model_factory.create_model()
    strategy = get_strategy(strategy_name)
    return strategy.build_graph(
        skill=skill,
        model=model,
        checkpointer=checkpointer_factory.saver,
    )


__all__ = ["build_graph", "DEFAULT_STRATEGY"]
