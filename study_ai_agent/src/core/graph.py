"""图构建器 - 共享的 LangGraph 框架，按 skill 参数化。

PPAS 图对每个 skill 都是一样的::

        START
          │
          ▼
      planner
          │
          ▼
      executor
          │
          ▼
      reviewer
          │              │
          ▼              ▼
      aggregator       planner    （revise 循环回来，由 LangGraph 的
          │                          recursion_limit 控制上限）
          ▼
         END

每个 skill 变化的是 *prompt* 和 *工具集*（以及 executor 上的 *HITL 策略*）。
本模块只暴露一个工厂 :func:`build_graph`，接受一个 :class:`SkillModule`
返回编译好的 :class:`~langgraph.graph.state.CompiledStateGraph`。
"""
# -*- coding: utf-8 -*-
from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.core.model_factory import model_factory
from src.core.nodes import (
    _route_after_review,
    make_aggregator_node,
    make_executor_node,
    make_planner_node,
    make_reviewer_node,
)
from src.core.skill import SkillModule
from src.core.state import AgentState


def build_graph(skill: SkillModule) -> CompiledStateGraph:
    """为给定 skill 编译 PPAS 图。

    chat model 在编译时解析一次，四个子 agent 共享。如果要 per-node
    用不同档位的模型，改 :mod:`src.core.nodes` 里的
    :func:`model_factory.create_model` 调用即可。
    """
    model, _provider_name = model_factory.create_model()

    g = StateGraph(AgentState)
    g.add_node("planner", make_planner_node(skill, model))
    g.add_node("executor", make_executor_node(skill, model))
    g.add_node("reviewer", make_reviewer_node(skill, model))
    g.add_node("aggregator", make_aggregator_node(skill))

    g.add_edge(START, "planner")
    g.add_edge("planner", "executor")
    g.add_edge("executor", "reviewer")
    g.add_conditional_edges(
        "reviewer",
        _route_after_review,
        {"planner": "planner", "aggregator": "aggregator"},
    )
    g.add_edge("aggregator", END)
    return g.compile(checkpointer=InMemorySaver())


__all__ = ["build_graph"]
