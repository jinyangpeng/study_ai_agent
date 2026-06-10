"""日志 middleware - 占位符。

LangChain 自带 :class:`LoggingMiddleware`，需要时 append 到这里。
空 list 让注册表在任何环境下都能 import。
"""
# -*- coding: utf-8 -*-
from __future__ import annotations

LOGGING_MIDDLEWARES: list = []

__all__ = ["LOGGING_MIDDLEWARES"]
