"""校验 middleware - tool 输入校验器的占位符。

在这里挂一个 ``Pydantic`` schema 或自定义的 :class:`AgentMiddleware` 子类。
空 list 让注册表在任何环境下都能 import。
"""

# -*- coding: utf-8 -*-
from __future__ import annotations

VALIDATION_MIDDLEWARES: list = []

__all__ = ["VALIDATION_MIDDLEWARES"]
