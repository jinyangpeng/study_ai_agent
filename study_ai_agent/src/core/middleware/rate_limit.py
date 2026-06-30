# -*- coding: utf-8 -*-
"""基于 IP 的滑动窗口限流中间件（#24）。

设计
----
* **滑动窗口** —— 用 ``deque`` 存最近请求时间戳，清理过期戳后计数
* **按 IP 隔离** —— 每个 IP 独立窗口，互不影响
* **可配置路径** —— 只对 ``RATE_LIMIT_PATHS`` 列出的端点前缀生效
* **内存实现** —— 单实例足够；多实例部署应前置 Nginx/网关做分布式限流
* **线程安全** —— 用锁保护 ``deque`` 操作
* **标准响应** —— 超限返回 ``429 Too Many Requests`` + ``Retry-After`` header +
  ``RATE_LIMITED`` error code（与 :mod:`src.core.errors` 对齐）

配置（环境变量）
----------------
RATE_LIMIT_ENABLED       true/false（默认 false，本地开发关）
RATE_LIMIT_PER_MINUTE    每分钟最大请求数（默认 60）
RATE_LIMIT_PATHS         限流端点前缀，逗号分隔（默认 "/,/api/chat,/admin/"）
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from threading import Lock
from typing import Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.config.settings import settings
from src.core.middleware.request_id import get_request_id

logger = logging.getLogger(__name__)

#: 限流响应的 error code（与 errors.py 的 _http_status_to_code 对齐）
_RATE_LIMITED_CODE = "RATE_LIMITED"


class _SlidingWindowCounter:
    """线程安全的滑动窗口计数器（按 IP 隔离）。

    每个窗口保留最近 ``window_seconds`` 秒内的请求时间戳，
    超过 ``max_requests`` 即触发限流。
    """

    def __init__(self, max_requests: int, window_seconds: float = 60.0):
        self._max = max_requests
        self._window = window_seconds
        self._lock = Lock()
        # IP -> deque[timestamp]
        self._buckets: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> tuple[bool, int, float]:
        """检查 ``key``（通常是 IP）是否允许通过。

        :returns: ``(allowed, remaining, retry_after_seconds)``
                  ``allowed=False`` 时 ``retry_after`` 是需要等待的秒数
        """
        now = time.time()
        cutoff = now - self._window
        with self._lock:
            bucket = self._buckets[key]
            # 清理过期戳
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self._max:
                # 计算最早一个戳什么时候过期 → retry_after
                retry_after = bucket[0] + self._window - now
                return False, 0, max(retry_after, 0.1)
            bucket.append(now)
            remaining = self._max - len(bucket)
            return True, remaining, 0.0

    def status(self) -> dict[str, int]:
        """返回当前跟踪的 IP 数 + 总请求数（供 /health 用）。"""
        with self._lock:
            return {
                "tracked_ips": len(self._buckets),
                "total_requests": sum(len(b) for b in self._buckets.values()),
            }


def _client_ip(request: Request) -> str:
    """提取客户端 IP（优先 ``X-Forwarded-For``，回退 ``client.host``）。"""
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        # X-Forwarded-For: client, proxy1, proxy2 → 取第一个
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _path_matches(path: str, prefixes: Iterable[str]) -> bool:
    """检查 ``path`` 是否以 ``prefixes`` 中任一项开头。"""
    return any(path == p or path.startswith(p) for p in prefixes if p)


#: 模块级单例计数器（中间件 + status 函数共用）
_counter: _SlidingWindowCounter | None = None


def _get_counter() -> _SlidingWindowCounter:
    """延迟初始化并返回模块级计数器单例。"""
    global _counter
    if _counter is None:
        _counter = _SlidingWindowCounter(
            max_requests=settings.RATE_LIMIT_PER_MINUTE,
            window_seconds=60.0,
        )
    return _counter


class RateLimitMiddleware(BaseHTTPMiddleware):
    """基于 IP 的滑动窗口限流中间件。

    配置通过 :class:`Settings` 读取：
    * ``RATE_LIMIT_ENABLED`` —— 总开关
    * ``RATE_LIMIT_PER_MINUTE`` —— 每分钟最大请求数
    * ``RATE_LIMIT_PATHS`` —— 限流端点前缀（逗号分隔）
    """

    def __init__(self, app, *args, **kwargs):
        super().__init__(app)
        self._enabled = settings.RATE_LIMIT_ENABLED
        self._counter = _get_counter()
        # 解析路径前缀列表
        self._paths = [
            p.strip() for p in settings.RATE_LIMIT_PATHS.split(",") if p.strip()
        ]
        if self._enabled:
            logger.info(
                "RateLimit 已启用: %d req/min, paths=%s",
                settings.RATE_LIMIT_PER_MINUTE, self._paths,
            )

    async def dispatch(self, request: Request, call_next) -> Response:
        # 未启用 / 非限流路径 → 直接放行
        if not self._enabled or not _path_matches(request.url.path, self._paths):
            return await call_next(request)

        ip = _client_ip(request)
        allowed, remaining, retry_after = self._counter.check(ip)
        if not allowed:
            rid = get_request_id()
            logger.warning(
                "Rate limit exceeded: ip=%s path=%s rid=%s retry_after=%.1fs",
                ip, request.url.path, rid, retry_after,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": _RATE_LIMITED_CODE,
                        "message": f"Rate limit exceeded. Retry after {retry_after:.1f}s.",
                        "request_id": rid,
                    }
                },
                headers={
                    "Retry-After": str(int(retry_after) + 1),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response


def rate_limit_status() -> dict:
    """返回限流器当前状态（供 /health 端点用）。"""
    if not settings.RATE_LIMIT_ENABLED:
        return {"enabled": False}
    return {
        "enabled": True,
        "per_minute": settings.RATE_LIMIT_PER_MINUTE,
        **_get_counter().status(),
    }


__all__ = [
    "RateLimitMiddleware",
    "rate_limit_status",
]
