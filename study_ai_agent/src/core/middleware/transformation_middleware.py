"""变换 middleware - 输入 / 输出变换器的占位符。

把改写消息的 :class:`AgentMiddleware` 子类（裁剪历史、规范化空白等）
放在这里。默认空。
"""

# -*- coding: utf-8 -*-
from __future__ import annotations

TRANSFORMATION_MIDDLEWARES: list = []

__all__ = ["TRANSFORMATION_MIDDLEWARES"]
