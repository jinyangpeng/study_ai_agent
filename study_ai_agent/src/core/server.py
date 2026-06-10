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
"""
# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

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
            async for event in request_agent.run(payload):
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
