"""Tool-level exception guard — 把工具异常转成结构化错误 JSON。

为什么需要
==========
之前 ``search_tools._ProxyAwareDuckDuckGoSearchResults._run`` 没有接住
``ddgs.exceptions.TimeoutException``，异常一路冒泡到 langgraph 的
``_runner.atick`` 触发 ``_panic_or_proceed``，整个 graph panic，AG-UI
SSE 流被掐断，前端收不到任何结果。

修法
----
包一层 ``_run`` / ``_arun``，捕获 ``Exception`` 后返回 JSON::

    {
        "ok": false,
        "tool": "<tool_name>",
        "error": "<type>:<message>",
        "args": {<被调用的参数摘要>}
    }

LLM 看到这份结构化错误就能优雅降级（"搜索服务暂不可用，
根据我已有知识 ..."），而不是让整个 graph 崩溃。

**重要边界**：只接 ``Exception``，不接 ``BaseException``。
``asyncio.CancelledError`` / ``KeyboardInterrupt`` 该冒泡还得冒泡。

使用
----
单个工具包一层（不修改原类）::

    from src.core.tools.safe_tool import make_safe
    search = make_safe(DuckDuckGoSearchResults())

或者子类化（如果还要叠加别的逻辑，比如 search_tools 里的代理）::

    from src.core.tools.safe_tool import SafeTool
    class MyTool(SafeTool, DuckDuckGoSearchResults):
        def _run(self, *args, **kwargs):
            with use_temp_env_proxy("..."):
                return super()._run(*args, **kwargs)
"""

# -*- coding: utf-8 -*-
from __future__ import annotations

import functools
import json
import logging

from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


def _summarise_args(args: tuple, kwargs: dict) -> dict:
    """把工具参数截成 ``<str>`` / ``<len N>`` 摘要，避免大 query 污染日志。"""
    out: dict[str, str] = {}
    if args:
        out["_args_0"] = str(args[0])[:120] if args[0] is not None else "None"
    for k, v in list(kwargs.items())[:4]:
        try:
            s = str(v)
        except Exception:
            s = f"<{type(v).__name__}>"
        out[k] = s[:120]
    return out


def _format_error_payload(tool_name: str, exc: Exception, args, kwargs) -> dict:
    """把异常格式化成结构化 dict（给 :func:`_format_error` / tuple 形式用）。"""
    return {
        "ok": False,
        "tool": tool_name,
        "error": f"{type(exc).__name__}: {exc}",
        "args": _summarise_args(args, kwargs),
        "hint": (
            "This tool call failed. Try: (1) rephrasing the query, "
            "(2) using a different tool, or (3) answering from prior knowledge."
        ),
    }


def _format_error(tool_name: str, exc: Exception, args, kwargs) -> str:
    """把异常格式化成 LLM 看得懂的结构化 JSON 字符串。

    注意：``DuckDuckGoSearchResults`` 等 ``response_format='content_and_artifact'``
    的工具，ToolNode 期望 ``_run`` 返回 ``(content, artifact)`` 2-tuple。
    本函数只返回 content 部分（字符串），调用方需要把它跟 artifact 配成
    2-tuple —— 详见 :func:`_format_error_tuple`。
    """
    return json.dumps(
        _format_error_payload(tool_name, exc, args, kwargs),
        ensure_ascii=False,
    )


def _format_error_tuple(tool_name: str, exc: Exception, args, kwargs) -> tuple[str, dict]:
    """返回 ``(content, artifact)`` 2-tuple，匹配 ``content_and_artifact`` 格式契约。

    适用于 :class:`DuckDuckGoSearchResults` /
    :class:`WikipediaQueryRun` 等 ``response_format='content_and_artifact'`` 的工具。
    ToolNode 看到 2-tuple 就不会再抛 ``ValueError: ... of type <class 'str'>``。
    """
    payload = _format_error_payload(tool_name, exc, args, kwargs)
    return _format_error(tool_name, exc, args, kwargs), payload


class SafeTool(BaseTool):
    """混入基类：在 ``_run`` / ``_arun`` 外层包 try/except。

    子类用 ``super()._run(...)`` 触发实际工具逻辑；本类把异常转成
    结构化 JSON 字符串返回。LLM 收到 JSON 后能自然处理。

    只接 ``Exception``，``BaseException``（CancelledError 等）原样上抛。
    """

    def _run(self, *args, **kwargs):  # type: ignore[override]
        try:
            return super()._run(*args, **kwargs)
        except Exception as exc:
            logger.warning(
                "tool %s._run failed: %s: %s (args=%s)",
                self.name,
                type(exc).__name__,
                exc,
                _summarise_args(args, kwargs),
            )
            return _safe_error_result(self, exc, args, kwargs)

    async def _arun(self, *args, **kwargs):  # type: ignore[override]
        try:
            return await super()._arun(*args, **kwargs)
        except Exception as exc:
            logger.warning(
                "tool %s._arun failed: %s: %s (args=%s)",
                self.name,
                type(exc).__name__,
                exc,
                _summarise_args(args, kwargs),
            )
            return _safe_error_result(self, exc, args, kwargs)


def _safe_error_result(tool: BaseTool, exc: Exception, args, kwargs):
    """根据工具的 ``response_format`` 返回对应形状的错误结果。

    * ``"content_and_artifact"`` —— ToolNode 期望 ``(content_str, artifact)`` 2-tuple
    * ``"content"``（默认）—— ToolNode 期望 ``str``

    不匹配的形状会被 ToolNode 抛 ``ValueError: ... of type <class 'str'>``
    之类的错误，掩盖真正的根因。
    """
    rf = getattr(tool, "response_format", "content")
    if rf == "content_and_artifact":
        return _format_error_tuple(tool.name, exc, args, kwargs)
    return _format_error(tool.name, exc, args, kwargs)


def make_safe(tool: BaseTool) -> BaseTool:
    """给一个已实例化的 :class:`BaseTool` 加异常防护。

    原地修改 ``_run`` / ``_arun``，返回同一个 tool 实例（便于链式调用）::

        search = make_safe(DuckDuckGoSearchResults())

    错误返回的形状**自动匹配**工具的 ``response_format``：
      * ``content_and_artifact`` → ``(error_json_str, error_dict)`` 2-tuple
      * 其它 → ``error_json_str`` 字符串

    实现用 :func:`functools.wraps` 保留原方法元数据（``__name__`` /
    ``__doc__`` / ``__wrapped__``），调试栈可读。
    """
    original_run = tool.__class__._run
    original_arun = getattr(tool.__class__, "_arun", None)

    @functools.wraps(original_run)
    def _safe_run(self, *args, **kwargs):  # noqa: ANN001
        try:
            return original_run(self, *args, **kwargs)
        except Exception as exc:
            logger.warning(
                "tool %s._run failed: %s: %s (args=%s)",
                tool.name,
                type(exc).__name__,
                exc,
                _summarise_args(args, kwargs),
            )
            return _safe_error_result(tool, exc, args, kwargs)

    @functools.wraps(original_arun) if original_arun else lambda f: f
    async def _safe_arun(self, *args, **kwargs):  # noqa: ANN001
        try:
            return await original_arun(self, *args, **kwargs)  # type: ignore[misc]
        except Exception as exc:
            logger.warning(
                "tool %s._arun failed: %s: %s (args=%s)",
                tool.name,
                type(exc).__name__,
                exc,
                _summarise_args(args, kwargs),
            )
            return _safe_error_result(tool, exc, args, kwargs)

    # 直接挂到实例上，不动类（避免影响其他同类工具）
    import types

    tool._run = types.MethodType(_safe_run, tool)
    if original_arun is not None:
        tool._arun = types.MethodType(_safe_arun, tool)
    return tool


__all__ = [
    "SafeTool",
    "make_safe",
    "_format_error",
    "_format_error_tuple",
    "_format_error_payload",
    "_safe_error_result",
    "_summarise_args",
]
