"""路由 middleware - 占位符。

在这里加供应商路由 / 降级逻辑（比如主供应商被限流时切到备用）。
默认空。
"""

# -*- coding: utf-8 -*-
from __future__ import annotations

ROUTING_MIDDLEWARES: list = []

__all__ = ["ROUTING_MIDDLEWARES"]
