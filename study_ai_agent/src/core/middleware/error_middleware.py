"""错误 middleware - 占位符。

需要的时候在这里加 :class:`RetryMiddleware` / :class:`FallbackMiddleware` /
:class:`CircuitBreakerMiddleware`。空默认让启动又快又没有副作用。
"""

# -*- coding: utf-8 -*-
from __future__ import annotations

ERROR_MIDDLEWARES: list = []

__all__ = ["ERROR_MIDDLEWARES"]
