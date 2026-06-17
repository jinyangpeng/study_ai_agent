"""上下文 middleware - 上下文增强策略的占位符。

需要追加 system 前置、附加 per-thread 元数据等场景时，把具体的
:class:`AgentMiddleware` 子类塞进来。保留一个空 list（而不是连模块都没有），
是为了让注册表能无脑引用这个符号。
"""

# -*- coding: utf-8 -*-
from __future__ import annotations

CONTEXT_MIDDLEWARES: list = []

__all__ = ["CONTEXT_MIDDLEWARES"]
