# -*- coding: utf-8 -*-
"""FastAPI server，把 LangGraph agent 通过 AG-UI 协议暴露出去。

架构
-----
* **运行时**   ：每个 skill 一个 LangGraph ``CompiledStateGraph``
                 （见 :mod:`src.core.graph`）
* **协议层**   ：AG-UI。事件是 ``ag-ui-protocol`` 中定义的 Pydantic 模型；
                 LangGraph -> AG-UI 事件翻译在官方的
                 ``ag-ui-langgraph`` 包里
* **传输**     ：FastAPI + SSE（``StreamingResponse`` + ``EventEncoder``）。
* **持久化**   ：PostgreSQL checkpointer（见 :mod:`src.core.checkpointer`），
                 由 FastAPI lifespan 在启动 / 关闭时分别 setup / aclose。

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

# ---------------------------------------------------------------------------
# Windows 兼容：psycopg3 async 必须用 SelectorEventLoop。
# ``asyncio.set_event_loop_policy`` 在 Python 3.16 将被移除，
# 推荐用 uvicorn ``loop_factory=``（见 ``src/__main__.py``）。
# 这里保留 policy 调用作为防御层 —— 任何不走 uvicorn ``loop_factory``
# 的入口（直接 ``python -m src.core.server``、测试、jupyter）依然能
# 拿到正确的 loop。warnings filter 把 3.14 的 DeprecationWarning 吞掉。
#
# ⚠️ 不要用 ``python -m uvicorn src.core.server:app``！那个会跳过
# ``src/__main__.py`` 的 loop_factory 注入，policy 也来不及生效（uvicorn
# 在 import 时就建好 Proactor loop 了）。正确启动方式：
#     python -m src
# ---------------------------------------------------------------------------
import asyncio  # noqa: E402
import sys as _sys  # noqa: E402

if _sys.platform == "win32":  # pragma: no cover
    import asyncio as _asyncio  # noqa: E402
    import warnings as _warnings  # noqa: E402

    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore", DeprecationWarning)
        try:
            _asyncio.set_event_loop_policy(_asyncio.WindowsSelectorEventLoopPolicy())
        except AttributeError:
            pass
    del _warnings
    del _asyncio
del _sys

import logging  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402
from functools import lru_cache  # noqa: E402
from typing import Any, AsyncIterator  # noqa: E402

from ag_ui.core.events import RunErrorEvent  # noqa: E402
from ag_ui.core.types import RunAgentInput  # noqa: E402
from ag_ui.encoder import EventEncoder  # noqa: E402
from ag_ui_langgraph import LangGraphAgent  # noqa: E402
from fastapi import FastAPI, HTTPException, Query, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse, StreamingResponse  # noqa: E402
from langchain_core.messages import BaseMessage  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from src.core.checkpointer import (  # noqa: E402
    _extract_text,
    checkpointer_factory,
)
from src.core.graph import build_graph  # noqa: E402
from src.core.skill import SkillModule  # noqa: E402

logger = logging.getLogger(__name__)

AGENT_NAME = "study_ai_agent"


# ---------------------------------------------------------------------------
# skill 注册表
# ---------------------------------------------------------------------------
# 懒加载，避免在包 import 时形成硬依赖循环。
# （core.server -> skills -> core.strategies -> core.skill 这条链本身没问题，
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
            detail=(f"Unknown skill '{skill_id}'. Available: {sorted(registry.keys())}"),
        )
    skill = registry[skill_id]
    return skill, build_graph(skill)


# ---------------------------------------------------------------------------
# SSE 事件过滤
# ---------------------------------------------------------------------------
# LangChain 1.x 的 ``create_agent(response_format=Plan/Review/Critique)`` 会在子图里
# 注册一个**合成**的 tool call：tool name = Pydantic 类名（"Plan" / "Review" / "Critique"），
# args = Pydantic 字段 JSON。这是为了把 LLM 的输出强约束成结构化 JSON，
# 实际数据流向是 ``state.plan`` / ``state.review`` / ``state.critique``（由 ``STATE_SNAPSHOT``
# 事件推到前端），**不**走 ``TOOL_CALL_RESULT``。
#
# ``ag-ui-langgraph`` 不区分"合成 tool"和"用户 tool"，会把所有 tool call
# 都按普通 tool 流出来。这导致前端 UI 多出"一个工具名 + 永远空 result"
# 的噪音块（args 长得很像 Plan / Review / Critique JSON，result 永远为空）。
#
# 我们的策略：维护一个 ``blocked_tool_call_ids`` 集合，TOOL_CALL_START 命中
# 内部白名单时把 id 加进去；之后所有引用该 id 的事件全部丢弃。
#
# 三个白名单项的来源：
#   * ``Plan``    — PERA 策略的 plan 节点输出
#   * ``Review``  — PERA 策略的 review 节点输出
#   * ``Critique``— Reflection 策略的 critique 节点输出
_STRUCTURED_OUTPUT_TOOL_NAMES: frozenset[str] = frozenset({"Plan", "Review", "Critique"})


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
@asynccontextmanager
async def _lifespan(app: FastAPI):
    """启动时初始化 checkpointer（开池 + 建表），关闭时优雅关池。

    失败策略：DB 不可达时直接抛 RuntimeError，让进程退出码 !=0。
    在容器编排里会被 kubelet / docker 自动重启；可观测性也更好。
    """
    await checkpointer_factory.setup()
    try:
        yield
    finally:
        await checkpointer_factory.aclose()


app = FastAPI(
    title="LangChain Agent API",
    version="1.0.0",
    description=(
        "基于 LangGraph + AG-UI 协议的多 skill 智能体后端。\n\n"
        "## 主要能力\n"
        "* **多 skill 调度** —— research / coding / qa，按 `forwarded_props.skill` 路由\n"
        "* **MCP 热插拔** —— 外部工具服务通过 `MCP_SERVERS` 配置接入，零代码扩展\n"
        "* **HITL 审批** —— 写操作工具自动触发人工审批门禁\n"
        "* **AG-UI 协议** —— SSE 事件流，兼容 assistant-ui 等前端\n\n"
        "## 健康检查\n"
        "* `GET /live` —— liveness probe（进程存活）\n"
        "* `GET /ready` —— readiness probe（依赖就绪）\n"
        "* `GET /health` —— 综合健康状态（含 checkpointer / MCP / 策略路由）\n"
    ),
    lifespan=_lifespan,
    contact={
        "name": "Study AI Agent Team",
        "url": "https://github.com/your-org/study_ai_agent",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    openapi_tags=[
        {"name": "AG-UI", "description": "AG-UI 协议端点（SSE 事件流）"},
        {"name": "Health", "description": "健康检查 / 存活 / 就绪探针"},
        {"name": "Skills", "description": "Skill 发现 / 热重载"},
        {"name": "Threads", "description": "会话历史管理"},
        {"name": "Legacy", "description": "旧版同步端点（保留兼容）"},
    ],
)

# ---------------------------------------------------------------------------
# 中间件注册（顺序：后注册的先执行）
# ---------------------------------------------------------------------------
# RequestIdMiddleware —— 为每条请求注入 request_id，贯穿日志 / 错误响应
from src.core.middleware.request_id import RequestIdMiddleware  # noqa: E402

app.add_middleware(RequestIdMiddleware)

# RateLimitMiddleware —— 基于 IP 的滑动窗口限流（#24）
# 默认关闭（RATE_LIMIT_ENABLED=false），生产环境通过环境变量开启
from src.core.middleware.rate_limit import RateLimitMiddleware  # noqa: E402

app.add_middleware(RateLimitMiddleware)

# CORS：本地开发默认全开。生产环境把 ``"*"`` 替换成显式的 allowlist 即可。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# 全局异常处理器 —— 统一错误响应格式 {"error": {"code", "message", "request_id"}}
# ---------------------------------------------------------------------------
from src.core.errors import register_exception_handlers  # noqa: E402

register_exception_handlers(app)


# ---------------------------------------------------------------------------
# 发现端点 - 让 AG-UI 前端可以渲染 skill 选择器
# ---------------------------------------------------------------------------
@app.get("/skeletons", tags=["Skills"])
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
# 管理端点 - 运行期热重载（不重启进程）
# ---------------------------------------------------------------------------
@app.post("/admin/skills/reload", tags=["Skills"])
async def reload_skills() -> dict[str, Any]:
    """热重载：重新拉 MCP 工具 + 清图缓存。

    使用场景：
    * CRM MCP server 重启 / 换了 URL 后，调一次让 agent 重新连
    * MCP_SERVERS 环境变量改了（需重启进程才能读新 env，此端点读
      的是当前进程已加载的 env；改 .env 后仍需重启进程）
    * 临时下线某个 MCP server 后清掉它的工具

    做两件事：
    1. integration_tools.reload() —— 重新连所有 MCP server，原地替换
       INTEGRATION_TOOLS 列表（保持引用不变）
    2. _compiled_graph_for.cache_clear() —— 清掉已编译图的 LRU 缓存，
       下一次请求会重新 build_graph()，从而读到新的工具集
    """
    from src.core.tools.integration_tools import reload as reload_mcp_tools

    new_tools = reload_mcp_tools()
    _compiled_graph_for.cache_clear()
    logger.info("Skills reloaded: %d MCP tools, graph cache cleared", len(new_tools))
    return {
        "reloaded": True,
        "mcp_tool_count": len(new_tools),
        "mcp_tool_names": [getattr(t, "name", str(t)) for t in new_tools],
        "graph_cache_cleared": True,
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


@app.post("/", tags=["AG-UI"])
async def run_agui(payload: RunAgentInput, request: Request):
    """在 ``forwarded_props.skill`` 声明的 skill 下运行 agent。

    body 是 :class:`ag_ui.core.RunAgentInput`（由 ``ag-ui-langgraph`` 校验），
    我们从 ``forwarded_props`` 中取出 skill id，把 AG-UI 事件以 SSE 流式
    返回。

    SSE 心跳（#7）：长时间无事件时（LLM 思考中、工具执行中）定期发
    ``: keep-alive`` 注释行，防代理 / 防火墙超时断开。间隔由
    ``SSE_HEARTBEAT_INTERVAL_SECONDS`` 配置（默认 15s，设 0 关闭）。
    """
    from src.config.settings import settings as _settings
    from src.core.sse_heartbeat import HEARTBEAT_LINE, is_heartbeat, with_heartbeat

    # #28 GraphRecursionError：LangGraph 递归超限异常
    try:
        from langgraph.errors import GraphRecursionError as _GraphRecursionError
    except ImportError:
        # 老版本 langgraph 可能没有这个异常类，用一个永远不会命中的兜底类
        class _GraphRecursionError(Exception):
            """兜底：langgraph.errors.GraphRecursionError 不可用时的占位。"""

    payload_dict = payload.model_dump()
    skill_id = _resolve_skill_id_from_input(payload_dict)
    request_agent = _agui_agent_for(skill_id).clone()
    encoder = EventEncoder(accept=request.headers.get("accept"))
    heartbeat_interval = _settings.SSE_HEARTBEAT_INTERVAL_SECONDS

    async def event_generator():
        # 关键修复：必须 try/except 包住整个迭代，并在异常时
        # yield 一个 RUN_ERROR 事件。否则 SSE 流会被裸掐断，浏览器侧
        # 会收到 ERR_INCOMPLETE_CHUNKED_ENCODING / "network error"。
        try:
            raw_events = request_agent.run(payload)
            # 过滤掉 LangChain ``create_agent(response_format=...)`` 产生的
            # 合成 tool call（参见 :func:`_filter_structured_output_tool_events`）。
            filtered = _filter_structured_output_tool_events(raw_events)
            # 叠加心跳（#7）：每 ``heartbeat_interval`` 秒无事件时发 keep-alive
            heartbeated = with_heartbeat(filtered, heartbeat_interval)
            async for item in heartbeated:
                if is_heartbeat(item):
                    yield HEARTBEAT_LINE
                else:
                    yield encoder.encode(item)
        except (asyncio.CancelledError, GeneratorExit):
            # SSE 客户端断开（关浏览器 / 切路由 / 网络掉）会触发
            # CancelledError（Python 3.8+ 是 BaseException 子类，
            # 不会被下面那条 ``except Exception`` 接住）。静默 return，
            # 不要走 RUN_ERROR 路径 —— 此时连接已经断了，再 yield 也送不到。
            logger.info("SSE 客户端断开，已停止事件流 (skill=%s)", skill_id)
            return
        except _GraphRecursionError:
            # #28 GraphRecursionError：图递归超限（PERA/Reflection 循环太多）
            # 不应裸掐断 SSE 流，前端需要知道是"步数超限"而非"服务挂了"。
            logger.warning(
                "GraphRecursionError: skill=%s recursion_limit=%s (调高 LANGGRAPH_RECURSION_LIMIT 或优化工具失败重试)",
                skill_id, _settings.LANGGRAPH_RECURSION_LIMIT,
            )
            err_event = RunErrorEvent(
                message=(
                    f"Agent reached recursion limit ({_settings.LANGGRAPH_RECURSION_LIMIT} steps). "
                    "The task may be too complex or a tool is failing repeatedly."
                ),
                code="RECURSION_LIMIT",
            )
            try:
                yield encoder.encode(err_event)
            except Exception:
                logger.warning("RECURSION_LIMIT 事件编码失败，SSE 流将直接关闭")
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
                # 编码失败也要保证流被关闭（让出控制权）
                logger.warning("RUN_ERROR 事件编码失败，SSE 流将直接关闭")
            # 函数正常返回 -> FastAPI 会发终止 chunk

    return StreamingResponse(
        event_generator(),
        media_type=encoder.get_content_type(),
    )


# ---------------------------------------------------------------------------
# Thread 历史 / 列表 / 删除 —— 配合 PostgreSQL checkpointer
# ---------------------------------------------------------------------------
# AG-UI 协议本身主要规定 ``POST /`` 的 SSE 事件流；thread 历史是 LangGraph
# 生态的常见扩展（参考 ``langgraph-sdk`` 的 ``/threads/{id}/state``）。
# 这里我们沿用同样的 REST 风格，但响应体**用 AG-UI 形状的 messages**：
#
#     { "id": "...", "role": "user|assistant|system|tool",
#       "content": "...", "tool_call_id": "...?", "tool_calls": [...]? }
#
# 字段名走 ``snake_case``（与 ``ag-ui-protocol`` 的 alias 兼容，前端按
# ``populate_by_name`` 也能解析）。tool_calls 用 OpenAI 形状，方便前端
# 直接喂给 assistant-ui 的 ToolCallMessagePart。
# ---------------------------------------------------------------------------

_LC_TO_AGUI_ROLE: dict[str, str] = {
    "HumanMessage": "user",
    "AIMessage": "assistant",
    "AIMessageChunk": "assistant",
    "SystemMessage": "system",
    "ToolMessage": "tool",
    "FunctionMessage": "tool",
}


def _lc_message_to_agui(msg: BaseMessage, idx: int) -> dict[str, Any]:
    """LangChain ``BaseMessage`` → AG-UI 形状 message。

    字段语义与 ``ag-ui-protocol`` 的 ``UserMessage`` / ``AssistantMessage``
    / ``ToolMessage`` 对齐；不识别的消息类归到 ``user``，避免丢消息。
    """
    cls_name = type(msg).__name__
    role = _LC_TO_AGUI_ROLE.get(cls_name, "user")

    out: dict[str, Any] = {
        # AG-UI 的 message 必须有 id；BaseMessage 默认没 id 时用 idx 兜底
        "id": getattr(msg, "id", None) or f"m-{idx}",
        "role": role,
        "content": _extract_text(msg.content),
    }

    # tool_calls：AIMessage 上的 OpenAI 风格
    if hasattr(msg, "tool_calls") and msg.tool_calls:
        out["tool_calls"] = [
            {
                "id": tc.get("id", ""),
                "type": "function",
                "function": {
                    "name": tc.get("name", ""),
                    # AG-UI ``ToolCall.function.arguments`` 是 str（JSON 字符串）
                    "arguments": (
                        tc.get("args") if isinstance(tc.get("args"), str) else _safe_json_dumps(tc.get("args", {}))
                    ),
                },
            }
            for tc in msg.tool_calls
        ]

    # tool result message：tool_call_id 必填
    if role == "tool" and getattr(msg, "tool_call_id", None):
        out["tool_call_id"] = msg.tool_call_id

    if getattr(msg, "name", None):
        out["name"] = msg.name

    return out


def _safe_json_dumps(obj: Any) -> str:
    import json

    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        logger.warning("_safe_json_dumps 序列化失败，返回空 JSON", exc_info=True)
        return "{}"


def _state_for_response(channel_values: dict[str, Any]) -> dict[str, Any]:
    """把 state 中的 Pydantic 模型 / 不可 JSON 化的字段规整成 dict。

    AG-UI 前端 ``STATE_SNAPSHOT`` 事件的 ``snapshot`` 字段是 ``Record<string, unknown>``，
    没法直接吃 Pydantic 实例；这里 ``model_dump()`` 一下。
    """
    out: dict[str, Any] = {}
    for k, v in channel_values.items():
        if k == "messages":
            continue  # messages 单独走 messages 字段
        if hasattr(v, "model_dump"):
            try:
                out[k] = v.model_dump()
                continue
            except Exception:
                logger.warning("model_dump 失败 (key=%s)，回退到 str()", k, exc_info=True)
        try:
            import json

            json.dumps(v, default=str)
            out[k] = v
        except Exception:
            out[k] = str(v)
    return out


@app.get("/threads", tags=["Threads"])
async def list_threads(
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    """列出 checkpointer 中所有 thread（最新 checkpoint 视角）。

    响应::

        {
          "threads": [
            {"thread_id", "checkpoint_id", "ts",
             "message_count", "first_user_message"}, ...
          ],
          "count": int
        }
    """
    threads = await checkpointer_factory.list_threads(limit=limit)
    return {"threads": threads, "count": len(threads)}


@app.get("/threads/{thread_id}/state", tags=["Threads"])
async def get_thread_state(thread_id: str) -> dict[str, Any]:
    """读取指定 thread 的最新 checkpoint state。

    响应：AG-UI 形状的 messages + LangGraph state 字段（plan / review / ...）。

    Returns 404 当 thread 不存在（从未写过 checkpoint）。
    """
    state = await checkpointer_factory.get_thread_state(thread_id)
    if state is None:
        raise HTTPException(
            status_code=404,
            detail=f"Thread not found: {thread_id}",
        )

    messages = [_lc_message_to_agui(m, idx) for idx, m in enumerate(state["messages"])]
    return {
        "thread_id": thread_id,
        "checkpoint_id": state["checkpoint_id"],
        "ts": state["ts"],
        "messages": messages,
        "state": _state_for_response(state["channel_values"]),
    }


@app.delete("/threads/{thread_id}", tags=["Threads"])
async def delete_thread(thread_id: str) -> dict[str, Any]:
    """删除一个 thread 的全部 checkpoint + writes（与前端删除会话语义对齐）。

    Returns 404 当 thread 不存在。
    """
    deleted = await checkpointer_factory.delete_thread(thread_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Thread not found: {thread_id}",
        )
    return {"deleted": True, "thread_id": thread_id}


# ---------------------------------------------------------------------------
# 健康检查 & 探针（#14）
# ---------------------------------------------------------------------------
# 三个端点的语义差异（Kubernetes / 容器编排标准）：
# * /live   —— liveness probe。进程还活着就 200，不检查依赖。
#              失败 → 编排系统重启容器。
# * /ready  —— readiness probe。依赖（DB / MCP）就绪才 200。
#              失败 → 编排系统把 pod 从 Service endpoints 摘掉（不重启）。
# * /health —— 综合健康状态，返回详细诊断信息。degraded 时返回 503，
#              便于监控告警 / 运维 dashboard 直接看状态码。
# ---------------------------------------------------------------------------
@app.get("/live", tags=["Health"])
async def liveness() -> dict:
    """Liveness probe —— 进程存活即 200（不检查依赖）。

    用于 Kubernetes livenessProbe / Docker HEALTHCHECK。
    失败时编排系统会重启容器。
    """
    return {"status": "alive", "agent": AGENT_NAME}


@app.get("/ready", tags=["Health"])
async def readiness() -> dict:
    """Readiness probe —— 依赖就绪才 200。

    检查项：
    * checkpointer（DB）可达
    * MCP server 断路器未全部打开（有 server 配置时）

    失败时编排系统会把 pod 从 Service endpoints 摘掉（不重启），
    等 ready 后再接流量。
    """
    cp_status = await checkpointer_factory.ping()
    cp_ok = cp_status.get("ok", False)

    from src.core.tools.integration_tools import mcp_health

    mcp_status = mcp_health()
    mcp_ok = True
    if mcp_status.get("configured") and mcp_status.get("tool_count", 0) == 0:
        mcp_ok = False

    ready = cp_ok and mcp_ok
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ready" if ready else "not_ready",
            "checkpointer": {"ok": cp_ok},
            "mcp": {"ok": mcp_ok, "configured": mcp_status.get("configured", False)},
        },
    )


@app.get("/health", tags=["Health"])
async def health() -> dict:
    """综合健康检查（含 checkpointer / DB / 策略路由 / MCP / 限流状态）。

    返回 200 当一切正常，503 当任何依赖 degraded。
    响应体含详细诊断信息，便于运维 dashboard / 监控告警使用。
    """
    cp_status = await checkpointer_factory.ping()
    cp_ok = cp_status.get("ok", False)

    # MCP 集成健康：tool_count + 每个 server 的断路器状态
    from src.core.tools.integration_tools import mcp_health

    mcp_status = mcp_health()
    # 只要有 server 配置但 tool_count=0 或任意断路器打开 → 视为 degraded
    mcp_ok = True
    if mcp_status.get("configured"):
        if mcp_status.get("tool_count", 0) == 0:
            mcp_ok = False
        for srv_info in mcp_status.get("servers", {}).values():
            if srv_info.get("circuit_open", False):
                mcp_ok = False
                break

    # 限流状态（#24）
    from src.core.middleware.rate_limit import rate_limit_status

    rl_status = rate_limit_status()

    overall_ok = cp_ok and mcp_ok

    # 暴露每个 skill 实际绑定的策略名 + 全局可用策略列表。
    # 便于运维一眼看清"qa 走 PERA、coding 走 ReAct"这种路由，
    # 排查"为什么这个 skill 反应这么慢"时也直接看 strategy 就能定位拓扑。
    from src.core.strategies import available as available_strategies
    from src.skills import SKILL_REGISTRY

    body = {
        "status": "ok" if overall_ok else "degraded",
        "agent": {"name": AGENT_NAME},
        "protocol": "ag-ui",
        "default_skill": _default_skill_id(),
        "checkpointer": cp_status,
        "mcp": mcp_status,
        "rate_limit": rl_status,
        "strategies": {
            "available": available_strategies(),
            "per_skill": {
                sid: {
                    "name": s.name,
                    "strategy": s.strategy,
                }
                for sid, s in SKILL_REGISTRY.items()
            },
        },
    }
    return JSONResponse(
        status_code=200 if overall_ok else 503,
        content=body,
    )


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


@app.post("/api/chat", response_model=ChatResponse, tags=["Legacy"])
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
    import asyncio
    import selectors
    import sys

    import uvicorn

    def _loop_factory() -> asyncio.AbstractEventLoop:
        # Windows 上 psycopg3 async 必须用 SelectorEventLoop；
        # uvicorn 默认会装 ProactorEventLoop，需要手动注入。
        if sys.platform == "win32":
            return asyncio.SelectorEventLoop(selectors.SelectSelector())
        return asyncio.DefaultEventLoop()

    from src.config.settings import settings

    uvicorn.run(
        "src.core.server:app",
        host=settings.HOST,
        port=settings.PORT,
        log_level=settings.LOG_LEVEL.lower(),
        # uvicorn 0.30+ 的 ``loop`` 可直接接收 loop factory
        loop=_loop_factory,
    )
