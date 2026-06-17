"""测试 middleware - 仅测试用插桩的占位符。

测试可以在此注册一个自定义 :class:`AgentMiddleware` 来捕获 agent 经历的
状态转移。默认空。
"""

# -*- coding: utf-8 -*-
from __future__ import annotations

TESTING_MIDDLEWARES: list = []

__all__ = ["TESTING_MIDDLEWARES"]
