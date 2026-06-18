"""Plan-Execute-Review-Act 推理策略。

拓扑图
======

::

        START
          │
          ▼
        plan
          │
          ▼
        execute
          │
          ▼
        review
          │              │
          ▼              ▼
         act           plan      （review 决定 revise 时循环回来，
          │                          由 LangGraph 的 recursion_limit 控上限）
          ▼
         END

设计要点
========
* 每个节点都是一个 ``async def node(state) -> dict``，匹配 LangGraph 节点签名。
  这些函数都是 :meth:`PerAStrategy._make_*_node` 的工厂返回，工厂把当前
  skill 的 prompt / 工具 / middleware 绑死，每次 skill 切换得到全新闭包。
* :meth:`build_graph` 只负责把节点连成拓扑，**不**创建 model / checkpointer
  —— 这两个由调用方注入（见 :class:`BaseStrategy` 注释）。
* ``_route_after_review`` 把 ``Review.verdict`` 映射到下一节点：
  ``approve`` -> ``act``，``revise`` -> ``plan``（循环到上限由
  ``recursion_limit`` 兜底）。
* 共享 helper（middleware 构造 / 文本抽取）走 :mod:`src.core.strategies.base`，
  这里只放 PERA 专属的拓扑 / 工厂。
"""

# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import logging

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.core.schemas import Plan, Review
from src.core.skill import SkillModule
from src.core.state import AgentState
from src.core.strategies.base import (
    BaseStrategy,
    NodeFn,
    build_skill_middleware,
    extract_structured,
    extract_text_from_message,
)

__all__ = [
    "PerAStrategy",
    "make_plan_node",
    "make_execute_node",
    "make_review_node",
    "make_act_node",
    "_route_after_review",
]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 各节点的工厂（Plan-Execute-Review-Act 架构的四个节点）
#
# 同时以模块级函数形式导出，兼容直接 ``from .p_e_r_a import make_plan_node``
# 的调用方（很多老测试就这么写的）。函数内部其实就是调类方法。
# ---------------------------------------------------------------------------
def make_plan_node(skill: SkillModule, model) -> NodeFn:
    """见 :meth:`PerAStrategy._make_plan_node`。"""
    return PerAStrategy._make_plan_node(skill, model)


def make_execute_node(skill: SkillModule, model) -> NodeFn:
    return PerAStrategy._make_execute_node(skill, model)


def make_review_node(skill: SkillModule, model) -> NodeFn:
    return PerAStrategy._make_review_node(skill, model)


def make_act_node(skill: SkillModule) -> NodeFn:
    return PerAStrategy._make_act_node(skill)


def _route_after_review(state: AgentState) -> str:
    """条件边：``approve`` -> act，``revise`` -> plan。"""
    review = state.get("review")
    if review is not None and review.verdict == "revise":
        return "plan"
    return "act"


# ---------------------------------------------------------------------------
# 策略类
# ---------------------------------------------------------------------------
class PerAStrategy(BaseStrategy):
    """Plan-Execute-Review-Act 策略。

    四阶段流水线：
    1. **plan** —— 不带工具，纯推理，输出 :class:`Plan`。
    2. **execute** —— 带 skill 工具集 + HITL 中间件，产出执行轨迹。
    3. **review** —— 不带工具，输出 :class:`Review`，决定 approve / revise。
    4. **act** —— 把 execute 的最后一条消息整理成 final_answer，append 一条
       ``AIMessage`` 让 AG-UI 聊天记录里看到最终答案。
    """

    name = "p_e_r_a"

    # ---- 公开 API ----
    def build_graph(
        self,
        skill: SkillModule,
        model,
        checkpointer=None,
    ) -> CompiledStateGraph:
        """为给定 skill + model 编译 PERA 图。

        ``checkpointer`` 透传给 :meth:`StateGraph.compile`；传 ``None``
        等同于无状态（仅适合 dev / 单测）。
        """
        g = StateGraph(AgentState)
        g.add_node("plan", self._make_plan_node(skill, model))
        g.add_node("execute", self._make_execute_node(skill, model))
        g.add_node("review", self._make_review_node(skill, model))
        g.add_node("act", self._make_act_node(skill))

        g.add_edge(START, "plan")
        g.add_edge("plan", "execute")
        g.add_edge("execute", "review")
        g.add_conditional_edges(
            "review",
            _route_after_review,
            {"plan": "plan", "act": "act"},
        )
        g.add_edge("act", END)
        return g.compile(checkpointer=checkpointer)

    # ---- 节点工厂（静态方法 —— 无状态，方便单测 / 复用） ----
    @staticmethod
    def _make_plan_node(skill: SkillModule, model) -> NodeFn:
        """构建一个使用 skill 的 ``plan_prompt`` 的 plan 节点。

        plan 永远不带工具 —— 规划是纯推理步骤。输出是一个 :class:`Plan`
        Pydantic 模型。
        """
        agent = create_agent(
            model=model,
            system_prompt=skill.plan_prompt,
            response_format=Plan,
            tools=[],
            middleware=build_skill_middleware(skill),
        )

        async def plan_node(state: AgentState) -> dict:
            result = await agent.ainvoke({"messages": state["messages"]})
            plan = extract_structured(result, Plan)
            return {"plan": plan, "messages": result["messages"]}

        return plan_node

    @staticmethod
    def _make_execute_node(skill: SkillModule, model) -> NodeFn:
        """构建一个带 skill 工具集和 middleware 的 execute 节点。"""
        tools = list(skill.tools)
        middleware = build_skill_middleware(skill)
        agent = create_agent(
            model=model,
            system_prompt=skill.execute_prompt,
            tools=tools,
            middleware=middleware,
        )

        async def execute_node(state: AgentState) -> dict:
            plan_payload = state.get("plan")
            # 把结构化 plan 作为 HumanMessage 拼到前面，让 execute 拿到完整 plan，
            # 不用再从 state 解析。
            plan_msg = HumanMessage(
                content=(
                    "Plan to execute:\n"
                    f"```json\n{json.dumps(plan_payload.model_dump(), ensure_ascii=False, indent=2)}\n```"
                )
                if plan_payload is not None
                else "Execute the user's request."
            )
            messages_in = state["messages"] + [plan_msg]
            # region debug-point execute-entry
            # 插桩：记录 model/tools/messages 数量，方便定位"模型在生成什么 tool_call 时炸了"
            try:
                _model_name = getattr(model, "model_name", None) or getattr(model, "model", "<unknown>")
            except Exception:
                _model_name = "<unknown>"
            logger.info(
                "[dbg][execute] model=%s tools=%s messages_in=%d",
                _model_name,
                [t.name for t in tools],
                len(messages_in),
            )
            # endregion
            try:
                result = await agent.ainvoke({"messages": messages_in})
            except Exception as _exc:
                # region debug-point execute-error
                # 插桩：APIError 时把"出错前的最后几条消息"和"异常 body"打出来
                import openai  # 局部 import 避免污染顶层依赖

                if isinstance(_exc, openai.APIError):
                    logger.error(
                        "[dbg][execute] APIError: status=%s code=%s type=%s message=%s request_id=%s",
                        getattr(_exc, "status_code", None),
                        getattr(_exc, "code", None),
                        getattr(_exc, "type", None),
                        str(_exc)[:500],
                        getattr(_exc, "request_id", None),
                    )
                    # 上游响应体（如有）—— 通常包含具体哪个 function.arguments 非法
                    body = getattr(_exc, "body", None)
                    if body is not None:
                        logger.error("[dbg][execute] error body=%s", str(body)[:800])
                # 打印最近 3 条消息摘要，便于定位"是哪个 tool 结果把模型喂崩了"
                tail = messages_in[-3:] if len(messages_in) > 3 else messages_in
                for i, m in enumerate(tail):
                    logger.error(
                        "[dbg][execute] msg[-%d] type=%s content[:200]=%s",
                        len(messages_in) - i,
                        type(m).__name__,
                        str(getattr(m, "content", ""))[:200],
                    )
                # endregion
                raise
            return {"messages": result["messages"]}

        return execute_node

    @staticmethod
    def _make_review_node(skill: SkillModule, model) -> NodeFn:
        """构建一个产出 :class:`Review` Pydantic 模型的 review 节点。"""
        agent = create_agent(
            model=model,
            system_prompt=skill.review_prompt,
            response_format=Review,
            tools=[],
            middleware=build_skill_middleware(skill),
        )

        async def review_node(state: AgentState) -> dict:
            result = await agent.ainvoke({"messages": state["messages"]})
            review = extract_structured(result, Review)
            return {"review": review, "messages": result["messages"]}

        return review_node

    @staticmethod
    def _make_act_node(skill: SkillModule) -> NodeFn:
        """构建发布 execute 最后一条消息的 act 节点。

        act 总是把一条 ``AIMessage`` append 到 ``messages``（让 AG-UI 在聊天
        记录里看到最终答案），并把原始文本存到 ``final_answer``。skill 可以通过
        :meth:`SkillModule.transform_final_answer` 覆盖最终字符串。
        """

        async def act_node(state: AgentState) -> dict:
            messages = state.get("messages", [])
            last = messages[-1] if messages else None
            raw = extract_text_from_message(last)
            final = skill.transform_final_answer(raw)
            return {"final_answer": final, "messages": [AIMessage(content=final)]}

        return act_node
