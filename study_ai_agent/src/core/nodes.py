"""per-skill 节点工厂。

每个工厂返回一个 ``async def node(state) -> dict`` 函数，匹配
``StateGraph`` 的节点签名。工厂接受一个 :class:`SkillModule`，
这样每个节点（planner / executor / reviewer / aggregator）都按当前
skill 的工具和 prompt 来参数化。

为什么用工厂（而不是普通函数）？
* 不同 skill 拿到不同 prompt / 工具集，但走同一种 wire 格式
  （input -> state，output -> dict）。工厂让参数化在调用点显而易见。
* ``create_agent`` 每次调用都构建一个 compiled sub-graph —— 这里不缓存，
  加载一个 *不同* 的 skill（也就是不同 prompt）就完全自由，不需要清空缓存。

LangChain 1.x 的关键点
----------------------
* ``create_agent(response_format=Plan)`` 会附加一个最终的结构化输出节点。
  我们通过 ``result["structured_response"]`` 取结果；如果该字段不存在，
  就回退到解析最后一条消息的文本。
"""
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from typing import Callable

from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    HumanInTheLoopMiddleware,
)
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import BaseTool
from pydantic import BaseModel

from src.core.middleware import BASE_MIDDLEWARES
from src.core.schemas import Plan, Review
from src.core.skill import SkillModule
from src.core.state import AgentState

NodeFn = Callable[[AgentState], dict]


# ---------------------------------------------------------------------------
# 共享 helper
# ---------------------------------------------------------------------------
def _extract_structured(result: dict, model_cls: type[BaseModel]) -> BaseModel:
    """从 ``response_format=`` 运行结果中提取已校验的 Pydantic 实例。

    LangChain 1.x 的 ``response_format=Model`` 会附加一个最终节点，把最后
    ``AIMessage`` 的 tool calls 解析成 ``structured_response`` 字段。
    找不到时回退到最后一条消息的文本（兼容更老的 tool-call 形状）。
    """
    structured = result.get("structured_response")
    if structured is not None:
        return structured
    messages = result.get("messages", [])
    last = messages[-1] if messages else None
    text = getattr(last, "text", lambda: getattr(last, "content", ""))()
    if isinstance(text, list):
        text = "".join(
            part.get("text", "") for part in text if isinstance(part, dict)
        )
    return model_cls.model_validate_json(str(text))


def _build_executor_middleware(skill: SkillModule) -> list[AgentMiddleware]:
    """组装 executor 的 middleware 栈：

    * 共享的基栈（``BASE_MIDDLEWARES`` —— 不含 HITL 闸门）
    * 一个 :class:`HumanInTheLoopMiddleware` 实例，其 ``interrupt_on``
      映射是 skill 的 per-tool 策略。

    每次 skill 调用都返回新 list，避免 skill 之间互相串味。
    """
    middlewares: list[AgentMiddleware] = list(BASE_MIDDLEWARES)
    hitl_rules = skill.hitl_rules
    if hitl_rules:
        middlewares.append(
            HumanInTheLoopMiddleware(interrupt_on=hitl_rules),
        )
    return middlewares


# ---------------------------------------------------------------------------
# 各节点的工厂
# ---------------------------------------------------------------------------
def make_planner_node(
    skill: SkillModule,
    model,
) -> NodeFn:
    """构建一个使用 skill 的 ``planner_prompt`` 的 planner 节点。

    planner 永远不带工具 —— 规划是纯推理步骤。输出是一个 :class:`Plan`
    Pydantic 模型。
    """
    agent = create_agent(
        model=model,
        system_prompt=skill.planner_prompt,
        response_format=Plan,
        tools=[],
    )

    async def planner_node(state: AgentState) -> dict:
        result = await agent.ainvoke({"messages": state["messages"]})
        plan = _extract_structured(result, Plan)
        return {"plan": plan, "messages": result["messages"]}

    return planner_node


def make_executor_node(
    skill: SkillModule,
    model,
) -> NodeFn:
    """构建一个带 skill 工具集和 middleware 的 executor 节点。"""
    tools: list[BaseTool] = list(skill.tools)
    middleware = _build_executor_middleware(skill)
    agent = create_agent(
        model=model,
        system_prompt=skill.executor_prompt,
        tools=tools,
        middleware=middleware,
    )

    async def executor_node(state: AgentState) -> dict:
        plan_payload = state.get("plan")
        # 把结构化 plan 作为 HumanMessage 拼到前面，让 executor 拿到完整 plan，
        # 不用再从 state 解析。
        plan_msg = HumanMessage(
            content=(
                "Plan to execute:\n"
                f"```json\n{json.dumps(plan_payload.model_dump(), ensure_ascii=False, indent=2)}\n```"
            )
            if plan_payload is not None
            else "Execute the user's request."
        )
        result = await agent.ainvoke(
            {"messages": state["messages"] + [plan_msg]}
        )
        return {"messages": result["messages"]}

    return executor_node


def make_reviewer_node(
    skill: SkillModule,
    model,
) -> NodeFn:
    """构建一个产出 :class:`Review` Pydantic 模型的 reviewer 节点。"""
    agent = create_agent(
        model=model,
        system_prompt=skill.reviewer_prompt,
        response_format=Review,
        tools=[],
    )

    async def reviewer_node(state: AgentState) -> dict:
        result = await agent.ainvoke({"messages": state["messages"]})
        review = _extract_structured(result, Review)
        return {"review": review, "messages": result["messages"]}

    return reviewer_node


def make_aggregator_node(skill: SkillModule) -> NodeFn:
    """构建发布 executor 最后一条消息的 aggregator。

    aggregator 总是把一条 ``AIMessage`` append 到 ``messages``（让 AG-UI 在聊天
    记录里看到最终答案），并把原始文本存到 ``final_answer``。skill 可以通过
    :meth:`SkillModule.transform_final_answer` 覆盖最终字符串。
    """

    async def aggregator_node(state: AgentState) -> dict:
        messages = state.get("messages", [])
        last = messages[-1] if messages else None
        if last is None:
            raw = ""
        elif isinstance(last.content, str):
            raw = last.content
        elif isinstance(last.content, list):
            raw = "".join(
                part.get("text", "")
                for part in last.content
                if isinstance(part, dict)
            )
        else:
            raw = str(last.content)
        final = skill.transform_final_answer(raw)
        return {"final_answer": final, "messages": [AIMessage(content=final)]}

    return aggregator_node


def _route_after_review(state: AgentState) -> str:
    """条件边：``approve`` -> aggregator，``revise`` -> planner。"""
    review = state.get("review")
    if review is not None and review.verdict == "revise":
        return "planner"
    return "aggregator"


__all__ = [
    "NodeFn",
    "make_planner_node",
    "make_executor_node",
    "make_reviewer_node",
    "make_aggregator_node",
    "_route_after_review",
]
