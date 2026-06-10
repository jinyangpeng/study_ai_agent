"""持久化 middleware - 占位符。

把往历史存储（数据库、Redis、文件）写入的自定义 :class:`AgentMiddleware`
放这里。默认空。
"""
# -*- coding: utf-8 -*-
from __future__ import annotations

PERSISTENCE_MIDDLEWARES: list = []

__all__ = ["PERSISTENCE_MIDDLEWARES"]
