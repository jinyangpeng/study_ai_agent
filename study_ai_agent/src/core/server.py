"""FastAPI server，把 LangGraph agent 通过 AG-UI 协议暴露出去。

架构
----
* **运行时**   ：每个 skill 一个 LangGraph ``CompiledStateGraph``
                 （见 :mod:`src.core.graph`）
* **协议层**   ：AG-UI。事件是 ``ag-ui-protocol`` 中定义的 Pydantic 模型；
                 LangGraph -> AG-UI 事件翻译在官方的
                 ``ag-ui-langgraph`` 包里
* **传输**     ：FastAPI + SSE（``StreamingResponse`` + ``EventEncoder``）。

skill 调度
----------
AG-UI 的 ``RunAgentInput.forwarded_props`` 字段带一个 ``skill`` key
（例如 ``{"skill": "coding"}``）。server 拿它和
:data:`src.skills.SKILL_REGISTRY` 对照，请求时为每个 skill 装一个
``LangGraphAgent``。编译过的图会缓存（相同 skill 的二次调用复用同一个实例），
但 ``LangGraphAgent`` wrapper 本身每请求 clone 一次（避免 ``active_run`` 在
并发 run 之间泄漏）。

路由
----
GET   /health       - 健康检查
GET   /skeletons    - 列出可用的 skill（AG-UI 选择器用）
POST  /api/chat     - 旧的同步聊天（方便 curl 测试）
GET   /             - AG-UI 健康
POST  /             - AG-UI 运行端点（SSE 事件流）

SSE 事件过滤
------------
LangChain 1.x 的 ``create_agent(response_format=Plan/Review)`` 会在图里
额外注册一个**合成**的 tool call（tool name 就是 Pydantic 类名 ``Plan`` /
``Review``），用于把 LLM 的输出强约束成结构化 JSON。``ag-ui-langgraph`` 会
把这次合成调用作为普通 ``TOOL_CALL_*`` 事件转发到客户端，结果就是：
前端 UI 多出"一个工具 + 永远空 result"的噪音块（实际数据已经走
``STATE_SNAPSHOT`` 的 ``state.review`` / ``state.plan`` 推给前端）。
我们在 :func:`_filter_structured_output_tool_events` 里把这种合成 tool
调用的全部相关事件 (``TOOL_CALL_START/ARGS/END/RESULT``) 屏蔽掉，让协议
流更干净。
"""
# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, AsyncIterator

from ag_ui.core.events import RunErrorEvent
from ag_ui.core.types import RunAgentInput
from ag_ui.encoder import EventEncoder
from ag_ui_langgraph import LangGraphAgent
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.core.graph import build_graph
from src.core.skill import SkillModule

logger = logging.getLogger(__name__)

AGENT_NAME = "study_ai_agent"


# ---------------------------------------------------------------------------
# skill 注册表
# ---------------------------------------------------------------------------
# 懒加载，避免在包 import 时形成硬依赖循环。
# （core.server -> skills -> core.nodes -> core.skill 这条链本身没问题，
# 但在这里 eager import skills 会让任何 import ``src.core.server`` 的代码
# 都把全部 skill 模块拉进来 —— 我们保持懒加载。）
def _get_skill_registry() -> dict[str, SkillModule]:
    from src.skills import SKILL_REGISTRY

    return SKILL_REGISTRY


def _default_skill_id() -> str:
    from src.skills import DEFAULT_SKILL_ID

    return DEFAULT_SKILL_ID


@lru_cache(maxsize=None)
def _compiled_graph_for(skill_id: str):
    """为指定 skill id 编译（并缓存）LangGraph。"""
    registry = _get_skill_registry()
    if skill_id not in registry:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown skill '{skill_id}'. "
                f"Available: {sorted(registry.keys())}"
            ),
        )
    skill = registry[skill_id]
    return skill, build_graph(skill)


# ---------------------------------------------------------------------------
# SSE 事件过滤
# ---------------------------------------------------------------------------
# LangChain 1.x 的 ``create_agent(response_format=Plan/Review)`` 会在子图里
# 注册一个**合成**的 tool call：tool name = Pydantic 类名（"Plan" / "Review"），
# args = Pydantic 字段 JSON。这是为了把 LLM 的输出强约束成结构化 JSON，
# 实际数据流向是 ``state.plan`` / ``state.review``（由 ``STATE_SNAPSHOT``
# 事件推到前端），**不**走 ``TOOL_CALL_RESULT``。
#
# ``ag-ui-langgraph`` 不区分"合成 tool"和"用户 tool"，会把所有 tool call
# 都按普通 tool 流出来。这导致前端 UI 多出"一个工具名 + 永远空 result"
# 的噪音块（args 长得很像 Plan / Review JSON，result 永远为空）。
#
# 我们的策略：维护一个 ``blocked_tool_call_ids`` 集合，TOOL_CALL_START 命中
# 内部白名单时把 id 加进去；之后所有引用该 id 的事件全部丢弃。
_STRUCTURED_OUTPUT_TOOL_NAMES: frozenset[str] = frozenset({"Plan", "Review"})


async def _filter_structured_output_tool_events(
    events: AsyncIterator[Any],
) -> AsyncIterator[Any]:
    """把 LangChain 合成结构化输出产生的 tool call 事件屏蔽掉。

    命中规则：``TOOL_CALL_START.tool_call_name in {Plan, Review}``。
    之后该 tool_call_id 对应的 ``TOOL_CALL_ARGS`` / ``TOOL_CALL_END`` /
    ``TOOL_CALL_RESULT`` 一并跳过。其它事件原样透传。
    """
    blocked: set[str] = set()
    async for event in events:
        ev_type = getattr(event, "type", None)
        if ev_type == "TOOL_CALL_START":
            name = getattr(event, "tool_call_name", None)
            tool_call_id = getattr(event, "tool_call_id", None)
            if name in _STRUCTURED_OUTPUT_TOOL_NAMES and tool_call_id:
                blocked.add(tool_call_id)
                logger.debug(
                    "filter structured-output tool call: name=%s id=%s",
                    name,
                    tool_call_id,
                )
                continue
            yield event
        elif ev_type in {
            "TOOL_CALL_ARGS",
            "TOOL_CALL_END",
            "TOOL_CALL_RESULT",
        }:
            tool_call_id = getattr(event, "tool_call_id", None)
            if tool_call_id in blocked:
                continue
            yield event
        else:
            yield event


# ---------------------------------------------------------------------------
# FastAPI 应用
# ---------------------------------------------------------------------------
app = FastAPI(title="LangChain Agent API")

# CORS：本地开发默认全开。生产环境把 ``"*"`` 替换成显式的 allowlist 即可。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# 发现端点 - 让 AG-UI 前端可以渲染 skill 选择器
# ---------------------------------------------------------------------------
@app.get("/skeletons")
async def list_skills() -> dict[str, Any]:
    """列出已注册的 skill（即 skeleton）。"""
    registry = _get_skill_registry()
    return {
        "default": _default_skill_id(),
        "skeletons": [
            {
                "id": skill.id,
                "name": skill.name,
                "description": skill.description,
                "tool_count": len(skill.tools),
                "hitl_rules": skill.hitl_rules,
                "quick_prompts": getattr(skill, "quick_prompts", []) or [],
            }
            for skill in registry.values()
        ],
    }


# ---------------------------------------------------------------------------
# AG-UI 协议挂载（一个端点，多个已编译的图）
# ---------------------------------------------------------------------------
def _agui_agent_for(skill_id: str) -> LangGraphAgent:
    """返回一个包装了 skill 图的 ``LangGraphAgent`` 实例（template）。

    每请求会 :meth:`LangGraphAgent.clone` 一次，避免底层已编译图的
    ``active_run`` 缓存在并发 run 之间泄漏。已编译图本身由
    :func:`_compiled_graph_for` 缓存。
    """
    skill, graph = _compiled_graph_for(skill_id)
    return LangGraphAgent(
        name=f"{AGENT_NAME}/{skill.id}",
        description=skill.description,
        graph=graph,
    )


def _resolve_skill_id_from_input(input_payload: dict[str, Any] | None) -> str:
    """从 AG-UI 请求 payload 中读出 skill id。

    ``forwarded_props`` 是 AG-UI 标准的应用层数据逃生舱。字段缺失或为
    空时回退到配置的默认值。
    """
    if not input_payload:
        return _default_skill_id()
    forwarded = input_payload.get("forwarded_props") or {}
    if not isinstance(forwarded, dict):
        return _default_skill_id()
    candidate = forwarded.get("skill") or forwarded.get("skeleton")
    if not candidate:
        return _default_skill_id()
    return str(candidate)


@app.post("/")
async def run_agui(payload: RunAgentInput, request: Request):
    """在 ``forwarded_props.skill`` 声明的 skill 下运行 agent。

    body 是 :class:`ag_ui.core.RunAgentInput`（由 ``ag-ui-langgraph`` 校验），
    我们从 ``forwarded_props`` 中取出 skill id，把 AG-UI 事件以 SSE 流式
    返回。
    """
    payload_dict = payload.model_dump()
    skill_id = _resolve_skill_id_from_input(payload_dict)
    request_agent = _agui_agent_for(skill_id).clone()
    encoder = EventEncoder(accept=request.headers.get("accept"))

    async def event_generator():
        # 关键修复：必须 try/except 包住整个迭代，并在异常时
        # yield 一个 RUN_ERROR 事件。否则 SSE 流会被裸掐断，浏览器侧
        # 会收到 ERR_INCOMPLETE_CHUNKED_ENCODING / "network error"。
        try:
            raw_events = request_agent.run(payload)
            # 过滤掉 LangChain ``create_agent(response_format=...)`` 产生的
            # 合成 tool call（参见 :func:`_filter_structured_output_tool_events`）。
            filtered = _filter_structured_output_tool_events(raw_events)
            async for event in filtered:
                yield encoder.encode(event)
        except Exception as exc:
            logger.exception("AG-UI run 异常，中断事件流")
            # 编码一个 RUN_ERROR 事件，让前端知道发生了什么
            err_event = RunErrorEvent(
                message=f"{type(exc).__name__}: {exc}",
                code="RUN_EXCEPTION",
            )
            try:
                yield encoder.encode(err_event)
            except Exception:
                # 即便编码失败也要保证流被关闭（让出控制权）
                pass
            # 函数正常返回 -> FastAPI 会发终止 chunk

    return StreamingResponse(
        event_generator(),
        media_type=encoder.get_content_type(),
    )


# ---------------------------------------------------------------------------
# 健康检查 & 旧端点
# ---------------------------------------------------------------------------
@app.get("/health")
async def health() -> dict:
    """健康检查。"""
    return {
        "status": "ok",
        "agent": {"name": AGENT_NAME},
        "protocol": "ag-ui",
        "default_skill": _default_skill_id(),
    }


class ChatRequest(BaseModel):
    """聊天请求（旧版）。"""

    message: str
    thread_id: str = "default"
    skill: str | None = None  # 可选的 skill 覆盖


class ChatResponse(BaseModel):
    """聊天响应（旧版）。"""

    reply: str
    thread_id: str
    skill: str


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    """简单的同步聊天端点（保留下来方便 curl 风格快速测试）。"""
    from langchain_core.runnables import RunnableConfig

    from src.core.logging_handler import LoggingHandler

    skill_id = req.skill or _default_skill_id()
    _skill, graph = _compiled_graph_for(skill_id)
    config: RunnableConfig = {
        "configurable": {"thread_id": req.thread_id},
        "callbacks": [LoggingHandler()],
    }
    inputs = {"messages": [{"role": "user", "content": req.message}]}
    result = await graph.ainvoke(inputs, config=config)
    messages = result.get("messages", [])
    last = messages[-1] if messages else None
    reply = last.content if hasattr(last, "content") else str(last)
    return ChatResponse(reply=reply, thread_id=req.thread_id, skill=skill_id)


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
