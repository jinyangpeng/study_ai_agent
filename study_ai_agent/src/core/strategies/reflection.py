"""Reflection (Generate / Critique / Refine) 推理策略。

拓扑图
======

::

        START
          │
          ▼
        generate           （LLM 产出初始 draft；可带工具调外部信息）
          │
          ▼
        critique           （LLM 评估：approve | revise + issues + suggestions）
          │
          ▼
        _should_refine     （verdict=revise 且未达 max -> refine；否则 act）
          │              │
          ▼              ▼
        refine           act
          │              │
          ▼              ▼
       critique        END
          ▲
          │（refine 把新 draft 写回 state["current_draft"]，
          │  路由回 critique 继续评审）

设计说明
========
* **三套 prompt**：generate / critique / refine 各自一个 system prompt，
  来自 :attr:`SkillModule.reflection_generate_prompt` 等；skill 不提供时
  回退到策略层默认（:data:`DEFAULT_REFLECTION_GENERATE_PROMPT` 等）。
* **iteration 上限**：state 里维护 ``reflection_iterations``，每次
  refine 后 +1。超过 :attr:`SkillModule.max_reflection_iterations`
  （默认 :data:`DEFAULT_MAX_REFLECTION_ITERATIONS` = 3）即使 critique
  还给 ``revise``，也强制 act —— 防止无限循环 / 死磕细节。
* **侧信道 ``current_draft``**：generate / refine 都把当前答案写到这里。
  critique 节点只产出结构化 verdict，不动 draft；act 节点从这里读最终 draft。
* **act 节点**：从 ``state["current_draft"]`` 读最终答案，走
  ``skill.transform_final_answer`` 推到 ``final_answer`` 字段，
  append 一条 :class:`AIMessage` 给 AG-UI 聊天记录。

与 ReAct / PERA 的区别
=====================
* **vs ReAct**：ReAct 在外部世界做（调工具查事实），无自我评审；
  Reflection 在自身答案上做（生成 → 评审 → 改写），可叠加在 ReAct
  之上当"答案质量把关"。
* **vs PERA**：PERA 关注"完成度 / 合规性"（plan → execute → review
  对照 plan 审计），Reflection 关注"答案质量"（生成 → 评审 → refine
  对照原始问题评价）。
"""
# -*- coding: utf-8 -*-
from __future__ import annotations

import json

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.core.schemas import Critique
from src.core.skill import SkillModule
from src.core.state import AgentState
from src.core.strategies.base import (
    DEFAULT_MAX_REFLECTION_ITERATIONS,
    BaseStrategy,
    NodeFn,
    build_skill_middleware,
    extract_structured,
    extract_text_from_message,
)

__all__ = [
    "ReflectionStrategy",
    "make_generate_node",
    "make_critique_node",
    "make_refine_node",
    "make_act_node",
    "should_refine",
    "DEFAULT_REFLECTION_GENERATE_PROMPT",
    "DEFAULT_REFLECTION_CRITIQUE_PROMPT",
    "DEFAULT_REFLECTION_REFINE_PROMPT",
]


# ---------------------------------------------------------------------------
# 策略级默认 prompt
# ---------------------------------------------------------------------------
DEFAULT_REFLECTION_GENERATE_PROMPT: str = (
    "You are the GENERATE step of a Reflection agent.\n"
    "Produce a clear, complete answer to the user's request.\n"
    "Use the available tools if you need external information; "
    "otherwise answer directly. Do not ask for clarification — commit to a draft."
)

DEFAULT_REFLECTION_CRITIQUE_PROMPT: str = (
    "You are the CRITIQUE step of a Reflection agent.\n"
    "Audit the current draft against the original question. Look for:\n"
    "  (1) factual errors or unsupported claims\n"
    "  (2) missing important angles or counterpoints\n"
    "  (3) unclear or poorly structured passages\n"
    "Output JSON with verdict='approve' (publishable as-is) or 'revise' "
    "(must be rewritten). If 'revise', name the specific gap in 'issues' and "
    "the concrete change you want in 'suggestions'. Be precise — vague feedback "
    "is not actionable."
)

DEFAULT_REFLECTION_REFINE_PROMPT: str = (
    "You are the REFINE step of a Reflection agent.\n"
    "You will receive: (1) the user's original question, (2) the current draft, "
    "(3) the critique's issues and suggestions.\n"
    "Produce a NEW, improved draft that addresses every concrete issue. "
    "Do not just patch; rewrite the affected sections cleanly. "
    "Use tools if you need to verify facts."
)


def _resolve_prompt(skill: SkillModule, attr: str, default: str) -> str:
    """skill 没显式提供对应 prompt 时回退到策略层默认。"""
    p = getattr(skill, attr, "") or ""
    return p if p.strip() else default


def _resolve_max_iterations(skill: SkillModule) -> int:
    """skill 没显式提供 max_reflection_iterations 时回退到默认 3。"""
    v = getattr(skill, "max_reflection_iterations", 0) or 0
    return v if v > 0 else DEFAULT_MAX_REFLECTION_ITERATIONS


# ---------------------------------------------------------------------------
# 模块级工厂 + 路由
# ---------------------------------------------------------------------------
def make_generate_node(skill: SkillModule, model) -> NodeFn:
    return ReflectionStrategy._make_generate_node(skill, model)


def make_critique_node(skill: SkillModule, model) -> NodeFn:
    return ReflectionStrategy._make_critique_node(skill, model)


def make_refine_node(skill: SkillModule, model) -> NodeFn:
    return ReflectionStrategy._make_refine_node(skill, model)


def make_act_node(skill: SkillModule) -> NodeFn:
    return ReflectionStrategy._make_act_node(skill)


def should_refine(state: AgentState) -> str:
    """条件边：``revise`` 且未达 max -> refine，否则 -> act。

    强制 act 的两种情况：
    1. critique.verdict == 'approve'（评审通过）
    2. reflection_iterations >= skill.max_reflection_iterations
       （达上限，避免无限循环）
    """
    critique = state.get("critique")
    iterations = state.get("reflection_iterations", 0) or 0
    # 注：skill 拿不到（路由是 module-level）—— 上限判断改在节点
    # 里通过 closure 捕获，见 :meth:`ReflectionStrategy.build_graph`。
    if critique is not None and critique.verdict == "revise":
        return "refine"
    return "act"


# ---------------------------------------------------------------------------
# 策略类
# ---------------------------------------------------------------------------
class ReflectionStrategy(BaseStrategy):
    """Generate / Critique / Refine 三阶段循环策略。"""

    name = "reflection"

    # ---- 公开 API ----
    def build_graph(
        self,
        skill: SkillModule,
        model,
        checkpointer=None,
    ) -> CompiledStateGraph:
        """为给定 skill + model 编译 Reflection 图。"""
        # 把 max_iterations 捕获到 closure，让路由函数能用到 skill 级别上限
        max_iters = _resolve_max_iterations(skill)
        prompt_iter = skill  # 占位，让 closure 读 skill

        def _route_after_critique(state: AgentState) -> str:
            critique = state.get("critique")
            iterations = state.get("reflection_iterations", 0) or 0
            if (
                critique is not None
                and critique.verdict == "revise"
                and iterations < max_iters
            ):
                return "refine"
            return "act"

        g = StateGraph(AgentState)
        g.add_node("generate", self._make_generate_node(skill, model))
        g.add_node("critique", self._make_critique_node(skill, model))
        g.add_node("refine", self._make_refine_node(skill, model))
        g.add_node("act", self._make_act_node(skill))

        g.add_edge(START, "generate")
        g.add_edge("generate", "critique")
        g.add_conditional_edges(
            "critique",
            _route_after_critique,
            {"refine": "refine", "act": "act"},
        )
        g.add_edge("refine", "critique")  # 改完再评审
        g.add_edge("act", END)
        return g.compile(checkpointer=checkpointer)

    # ---- 节点工厂 ----
    @staticmethod
    def _make_generate_node(skill: SkillModule, model) -> NodeFn:
        """生成首版 draft；带 skill 工具集（可调外部查资料）。"""
        tools = list(skill.tools)
        middleware = build_skill_middleware(skill)
        agent = create_agent(
            model=model,
            system_prompt=_resolve_prompt(
                skill, "reflection_generate_prompt", DEFAULT_REFLECTION_GENERATE_PROMPT,
            ),
            # tools=tools,
            tools=[],
            middleware=middleware,
        )

        async def generate_node(state: AgentState) -> dict:
            result = await agent.ainvoke({"messages": state["messages"]})
            last = result["messages"][-1] if result.get("messages") else None
            draft = extract_text_from_message(last)
            return {
                "current_draft": draft,
                "messages": result["messages"],
                "reflection_iterations": 0,  # 首版不算一轮 refine
            }

        return generate_node

    @staticmethod
    def _make_critique_node(skill: SkillModule, model) -> NodeFn:
        """评审当前 draft；不带工具，输出 :class:`Critique` 结构化结果。"""
        agent = create_agent(
            model=model,
            system_prompt=_resolve_prompt(
                skill, "reflection_critique_prompt", DEFAULT_REFLECTION_CRITIQUE_PROMPT,
            ),
            response_format=Critique,
            tools=[],
        )

        async def critique_node(state: AgentState) -> dict:
            result = await agent.ainvoke({"messages": state["messages"]})
            critique = extract_structured(result, Critique)
            return {"critique": critique, "messages": result["messages"]}

        return critique_node

    @staticmethod
    def _make_refine_node(skill: SkillModule, model) -> NodeFn:
        """根据 critique 重写 draft；带 skill 工具集（可调外部查证）。"""
        tools = list(skill.tools)
        middleware = build_skill_middleware(skill)
        agent = create_agent(
            model=model,
            system_prompt=_resolve_prompt(
                skill, "reflection_refine_prompt", DEFAULT_REFLECTION_REFINE_PROMPT,
            ),
            # tools=tools,
            tools=[],
            middleware=middleware,
        )

        async def refine_node(state: AgentState) -> dict:
            critique = state.get("critique")
            current_draft = state.get("current_draft", "") or ""
            iterations = state.get("reflection_iterations", 0) or 0

            # 把 draft + critique 拼成 HumanMessage 注入，模型能直接看到
            # 改写上下文（不用从 state 解析）。
            refine_msg = HumanMessage(
                content=(
                    "Current draft to improve:\n"
                    f"```\n{current_draft}\n```\n\n"
                    f"Critique verdict: {critique.verdict if critique else 'revise'}\n"
                    f"Issues:\n"
                    + "\n".join(f"- {x}" for x in (critique.issues if critique else []))
                    + "\n\nSuggestions:\n"
                    + "\n".join(f"- {x}" for x in (critique.suggestions if critique else []))
                    + "\n\nNow rewrite the draft to address every concrete issue."
                )
            )
            result = await agent.ainvoke(
                {"messages": state["messages"] + [refine_msg]}
            )
            new_last = result["messages"][-1] if result.get("messages") else None
            new_draft = extract_text_from_message(new_last)
            return {
                "current_draft": new_draft,
                "messages": result["messages"],
                "reflection_iterations": iterations + 1,
            }

        return refine_node

    @staticmethod
    def _make_act_node(skill: SkillModule) -> NodeFn:
        """从 ``state["current_draft"]`` 取最终答案推到 AG-UI。"""

        async def act_node(state: AgentState) -> dict:
            draft = state.get("current_draft", "") or ""
            final = skill.transform_final_answer(draft)
            return {
                "final_answer": final,
                "messages": [AIMessage(content=final)],
            }

        return act_node
