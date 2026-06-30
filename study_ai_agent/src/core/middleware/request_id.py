# -*- coding: utf-8 -*-
"""请求 ID 中间件 —— 为每条请求注入唯一 ``request_id``，贯穿日志 / 错误响应 / LLM 调用。

设计
----
* 用 :class:`contextvars.ContextVar` 存储 ``request_id``，async 安全
* 中间件从 ``X-Request-ID`` header 读取（允许上游传入），否则生成 12 位 hex
* :class:`RequestIdFilter` 把 ``request_id`` 注入到每条日志记录
* 错误响应通过 :func:`get_request_id` 读取当前 ID，回传给客户端

使用::

    # server.py
    from src.core.middleware.request_id import RequestIdMiddleware
    app.add_middleware(RequestIdMiddleware)

    # 任意位置
    from src.core.middleware.request_id import get_request_id
    rid = get_request_id()  # "a1b2c3d4e5f6"
"""
from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

#: 全局 request_id ContextVar。async 安全，每个请求独立。
request_id_var: ContextVar[str] = ContextVar("request_id", default="")

#: 响应头名称
REQUEST_ID_HEADER = "X-Request-ID"


def get_request_id() -> str:
    """获取当前请求的 ``request_id``（无请求上下文时返回空串）。"""
    return request_id_var.get("")


def _new_request_id() -> str:
    """生成 12 位 hex request_id。"""
    return uuid.uuid4().hex[:12]


class RequestIdMiddleware(BaseHTTPMiddleware):
    """读取 / 生成 ``X-Request-ID``，存入 ContextVar，写入响应头。"""

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get(REQUEST_ID_HEADER) or _new_request_id()
        token = request_id_var.set(rid)
        try:
            response: Response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = rid
            return response
        finally:
            request_id_var.reset(token)


class RequestIdFilter(logging.Filter):
    """把 ``request_id`` 注入到每条日志记录的 ``record.request_id`` 字段。

    配合 Formatter 里的 ``%(request_id)s`` 使用。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("")
        return True


__all__ = [
    "REQUEST_ID_HEADER",
    "RequestIdFilter",
    "RequestIdMiddleware",
    "get_request_id",
    "request_id_var",
]
