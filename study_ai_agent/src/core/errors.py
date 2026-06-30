# -*- coding: utf-8 -*-
"""统一错误处理 —— 业务异常类 + 全局异常处理器 + 标准错误响应格式。

设计
----
* :class:`AgentError` —— 业务异常基类，携带 ``code`` / ``message`` / ``status_code``
* :func:`register_exception_handlers` —— 注册到 FastAPI app，统一返回::

      {"error": {"code": "...", "message": "...", "request_id": "..."}}

* 客户端永远拿不到堆栈 / 内部模块名 / 文件路径，只拿到 ``code`` + ``message``
* 服务端日志通过 ``logger.exception`` 记录完整堆栈
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 错误响应模型
# ---------------------------------------------------------------------------
class ErrorDetail(BaseModel):
    """标准错误响应体（嵌在 ``{"error": ErrorDetail}`` 里）。"""

    code: str
    message: str
    request_id: str = ""
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    """HTTP 错误响应的顶层结构。"""

    error: ErrorDetail


# ---------------------------------------------------------------------------
# 业务异常类
# ---------------------------------------------------------------------------
class AgentError(Exception):
    """Agent 业务异常基类。

    用法::

        raise AgentError("SKILL_NOT_FOUND", f"Unknown skill: {sid}", 400)
    """

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)


# ---------------------------------------------------------------------------
# 全局异常处理器注册
# ---------------------------------------------------------------------------
def register_exception_handlers(app) -> None:
    """注册全局异常处理器到 FastAPI app。

    处理三类异常：
    1. :class:`AgentError` —— 业务异常，返回 ``exc.code`` + ``exc.message``
    2. :class:`HTTPException` —— FastAPI 内置异常，统一格式化
    3. :class:`Exception` —— 兜底，返回 ``INTERNAL`` + 通用消息（不泄露堆栈）
    """
    from src.core.middleware.request_id import get_request_id

    @app.exception_handler(AgentError)
    async def _handle_agent_error(request: Request, exc: AgentError) -> JSONResponse:
        rid = get_request_id()
        logger.warning(
            "AgentError: code=%s status=%s rid=%s msg=%s",
            exc.code, exc.status_code, rid, exc.message,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=ErrorDetail(
                    code=exc.code,
                    message=exc.message,
                    request_id=rid,
                    details=exc.details,
                )
            ).model_dump(),
        )

    @app.exception_handler(HTTPException)
    async def _handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        rid = get_request_id()
        # 把 FastAPI 默认的 {"detail": "..."} 统一成 {"error": {...}} 格式
        code = _http_status_to_code(exc.status_code)
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=ErrorDetail(
                    code=code,
                    message=str(exc.detail),
                    request_id=rid,
                )
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def _handle_generic_exception(request: Request, exc: Exception) -> JSONResponse:
        rid = get_request_id()
        # 服务端记录完整堆栈，客户端只拿通用消息
        logger.exception("Unhandled exception (rid=%s): %s", rid, type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="INTERNAL",
                    message="Internal server error",
                    request_id=rid,
                )
            ).model_dump(),
        )


def _http_status_to_code(status_code: int) -> str:
    """HTTP 状态码 → 错误 code 映射。"""
    mapping = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "UNPROCESSABLE_ENTITY",
        429: "RATE_LIMITED",
    }
    return mapping.get(status_code, f"HTTP_{status_code}")


__all__ = [
    "AgentError",
    "ErrorDetail",
    "ErrorResponse",
    "register_exception_handlers",
]
