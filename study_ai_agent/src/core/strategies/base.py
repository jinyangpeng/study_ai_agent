"""推理策略抽象基类 + 共享工具。

企业级要点
==========
* **类型化契约**：每个策略必须实现 :meth:`BaseStrategy.build_graph`，
  返回 :class:`~langgraph.graph.state.CompiledStateGraph`，IDE 能在调用点
  补全 + 静态检查。
* **零隐式依赖**：策略类不直接 import 任何具体的 LangGraph 拓扑构建函数，
  全部走自己的私有实现 —— 加新策略（ReAct / Reflection）时不需要碰老策略。
* **可插拔注册**：策略通过 :func:`src.core.strategies.register` 装饰器
  注册到全局表，外部模块可动态添加（解耦核心 + 业务）。

设计权衡
========
* :meth:`build_graph` 接受 ``model`` 和 ``checkpointer`` 作为参数 —— 策略不
  拥有 model_factory / checkpointer 的引用，所有"运行环境"由调用方注入。
  好处是：单测里可以传 mock model；多策略共享同一份 model / checkpointer
  时也不用重新构造。
* **共享 helper**（:func:`build_skill_middleware` / :func:`extract_text_from_message`
  / :func:`extract_structured`）放在基类模块 —— 三个策略都要用，
  避免在每个策略文件里复制粘贴。
"""

# -*- coding: utf-8 -*-
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Optional

from langchain.agents.middleware import AgentMiddleware, HumanInTheLoopMiddleware
from langchain_core.messages import BaseMessage
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

from src.core.middleware import BASE_MIDDLEWARES
from src.core.skill import SkillModule

__all__ = [
    "BaseStrategy",
    "NodeFn",
    "DEFAULT_MAX_REFLECTION_ITERATIONS",
    "extract_structured",
    "extract_text_from_message",
    "build_skill_middleware",
]

#: 节点函数签名：``async def node(state: AgentState) -> dict``。
NodeFn = Callable[[dict], dict]

#: Reflection 策略的 refine 循环默认上限（skill 不提供时回退到这）。
DEFAULT_MAX_REFLECTION_ITERATIONS: int = 3


class BaseStrategy(ABC):
    """推理策略抽象基类。

    每个具体策略（PERA / ReAct / Reflection / ...) 实现
    :meth:`build_graph`，给定一个 :class:`SkillModule` + chat model +
    可选 checkpointer，返回编译好的 LangGraph。
    """

    #: 策略名。注册到全局表时用这个 key。空字符串会在注册时抛错。
    name: str = ""

    @abstractmethod
    def build_graph(
        self,
        skill: SkillModule,
        model,
        checkpointer=None,
    ) -> CompiledStateGraph:
        """为给定 skill + model 编译并返回 LangGraph。

        Parameters
        ----------
        skill
            当前 skill 模块（prompt / 工具集 / HITL 规则）。
        model
            chat model 实例（由调用方用 ``model_factory.create_model()`` 构造）。
        checkpointer
            可选的 checkpointer（如 ``checkpointer_factory.saver``），
            传 ``None`` 表示无状态（仅 dev / 测试用）。
        """
        ...


# ---------------------------------------------------------------------------
# 共享 helper
# ---------------------------------------------------------------------------
def build_skill_middleware(skill: SkillModule) -> list[AgentMiddleware]:
    """组装 skill 的 middleware 栈：

    * 共享的基栈（``BASE_MIDDLEWARES`` —— 不含 HITL 闸门）
    * 一个 :class:`HumanInTheLoopMiddleware` 实例，其 ``interrupt_on``
      映射是 skill 的 per-tool 策略。

    每次 skill 调用都返回**新 list**，避免 skill 之间互相串味。PERA 的
    execute 节点、ReAct 的 react 节点、Reflection 的 generate / refine
    节点都走这个统一构造。
    """
    middlewares: list[AgentMiddleware] = list(BASE_MIDDLEWARES)
    hitl_rules = skill.hitl_rules
    if hitl_rules:
        middlewares.append(
            HumanInTheLoopMiddleware(interrupt_on=hitl_rules),
        )
    return middlewares


def extract_structured(
    result: dict,
    model_cls: type[BaseModel],
) -> BaseModel:
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
        text = "".join(part.get("text", "") for part in text if isinstance(part, dict))
    return model_cls.model_validate_json(str(text))


def extract_text_from_message(message: Optional[BaseMessage]) -> str:
    """从 AIMessage（或其他任何 :class:`BaseMessage`）里抽纯文本。

    * ``content`` 是 str —— 直接返回
    * ``content`` 是 list（多模态 / LangChain v1 的 content blocks）——
      拼出所有 ``{"type": "text", "text": "..."}`` 块
    * ``content`` 是 None / 其他 —— 走 ``str(content)`` 兜底
    """
    if message is None:
        return ""
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return str(content)
