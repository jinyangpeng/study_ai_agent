"""Human-in-the-loop middleware。

需要时在这里挂 :class:`HumanInTheLoopMiddleware`（或其自定义子类）。
默认保持空，让 agent 启动时不需要任何审批；把 import 打开即可启用闸门。
"""

# -*- coding: utf-8 -*-
from __future__ import annotations

HUMAN_IN_LOOP_MIDDLEWARES: list = []

__all__ = ["HUMAN_IN_LOOP_MIDDLEWARES"]
