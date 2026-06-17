"""ReAct (Reasoning + Acting) 推理策略。

拓扑图
======

::

        START
          │
          ▼
        react_agent       （LLM 思考 + 决策，可能产生 tool calls 或 final answer）
          │
          ▼
         act                （提取最终 answer，append AIMessage 推到 messages）
          │
          ▼
         END

设计说明
========
* 真正的 ReAct 循环（**Thought -> Action -> Observation -> ...**）在
  LangChain 1.x 的 :func:`create_agent` 内部已经实现 —— agent 节点会自己
  反复调模型、产生 tool calls、注入 ToolMessage，直到模型给出 final answer。
  我们不需要在 LangGraph 拓扑里手写 tools 节点 + 条件边 + 循环边，
  那只会和 create_agent 的内置循环重复。
* 与 PERA 的关键区别：ReAct **没有** plan / review 阶段 —— 直接进
  thought/act 循环。适合"任务明确、靠工具调用就能完成"的场景；
  不适合"需要先拆解再审计"的复杂任务（那是 PERA 的强项）。
* 与 Reflection 的关键区别：ReAct **没有** "自我评审 / 重写" 循环；
  ReAct 是在 *外部世界* 里做（调工具、查事实），Reflection 是在
  *自身答案* 上做（生成 → 评审 → 改写 → 评审 → ...）。
* ``act`` 节点从 messages 抽最后一条 AI 文本，走 skill 的
  ``transform_final_answer``，推到 ``final_answer`` 字段。
"""

# -*- coding: utf-8 -*-
from __future__ import annotations

from langchain.agents import create_agent
from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.core.skill import SkillModule
from src.core.state import AgentState
from src.core.strategies.base import (
    BaseStrategy,
    NodeFn,
    build_skill_middleware,
    extract_text_from_message,
)

__all__ = ["ReActStrategy", "make_react_node", "make_act_node", "DEFAULT_REACT_PROMPT"]


# ---------------------------------------------------------------------------
# 策略级默认 prompt
# ---------------------------------------------------------------------------
DEFAULT_REACT_PROMPT: str = (
    "You are a ReAct (Reasoning + Acting) agent.\n"
    "For each turn:\n"
    "  1. Think step by step about what you need to do.\n"
    "  2. If you need external information, CALL A TOOL — do not guess.\n"
    "  3. When the answer is ready, write it out as plain text (no tool call).\n"
    "Be concise. Quote exact tool results when they support a claim. "
    "If a tool returns no useful result, say so and try a different angle."
)


def _resolve_react_prompt(skill: SkillModule) -> str:
    """skill 没提供 ``react_prompt`` 时回退到 :data:`DEFAULT_REACT_PROMPT`。"""
    p = getattr(skill, "react_prompt", "") or ""
    return p if p.strip() else DEFAULT_REACT_PROMPT


# ---------------------------------------------------------------------------
# 模块级工厂（兼容老 import 风格）
# ---------------------------------------------------------------------------
def make_react_node(skill: SkillModule, model) -> NodeFn:
    """见 :meth:`ReActStrategy._make_react_node`。"""
    return ReActStrategy._make_react_node(skill, model)


def make_act_node(skill: SkillModule) -> NodeFn:
    return ReActStrategy._make_act_node(skill)


# ---------------------------------------------------------------------------
# 策略类
# ---------------------------------------------------------------------------
class ReActStrategy(BaseStrategy):
    """ReAct (Reasoning + Acting) 策略。

    最简推理形态：单 agent 节点内置 thought/act 循环 + act 节点收尾。
    没有 plan / review / refine 阶段。
    """

    name = "react"

    # ---- 公开 API ----
    def build_graph(
        self,
        skill: SkillModule,
        model,
        checkpointer=None,
    ) -> CompiledStateGraph:
        """为给定 skill + model 编译 ReAct 图。"""
        g = StateGraph(AgentState)
        g.add_node("react_agent", self._make_react_node(skill, model))
        g.add_node("act", self._make_act_node(skill))

        g.add_edge(START, "react_agent")
        g.add_edge("react_agent", "act")
        g.add_edge("act", END)
        return g.compile(checkpointer=checkpointer)

    # ---- 节点工厂 ----
    @staticmethod
    def _make_react_node(skill: SkillModule, model) -> NodeFn:
        """构建一个带 skill 工具集和 middleware 的 react 节点。

        agent 内部自带 ReAct 循环（thought -> tool call -> observation -> ...）。
        """
        tools = list(skill.tools)
        middleware = build_skill_middleware(skill)
        agent = create_agent(
            model=model,
            system_prompt=_resolve_react_prompt(skill),
            tools=tools,
            middleware=middleware,
        )

        async def react_node(state: AgentState) -> dict:
            result = await agent.ainvoke({"messages": state["messages"]})
            return {"messages": result["messages"]}

        return react_node

    @staticmethod
    def _make_act_node(skill: SkillModule) -> NodeFn:
        """把 react_agent 最后一条消息的纯文本作为 final_answer 推给 AG-UI。"""

        async def act_node(state: AgentState) -> dict:
            messages = state.get("messages", [])
            last = messages[-1] if messages else None
            raw = extract_text_from_message(last)
            final = skill.transform_final_answer(raw)
            return {"final_answer": final, "messages": [AIMessage(content=final)]}

        return act_node
