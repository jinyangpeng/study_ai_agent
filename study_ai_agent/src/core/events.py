"""AG-UI 事件的 re-export，让下游代码类型安全。

``ag-ui-protocol`` 中的 Pydantic 模型是 AG-UI 事件（:class:`BaseEvent`）和
请求包络（:class:`RunAgentInput`）的权威定义。本模块 re-export 我们会用到的
几个名字，这样调用方就不用直接依赖外部包——同时也是单一替换点，未来要换底层
库时只改这里。
"""
# -*- coding: utf-8 -*-
from __future__ import annotations

from ag_ui.core import (
    BaseEvent as AGUIEvent,
)
from ag_ui.core import (
    EventType as AGUIEventType,
)
from ag_ui.core import RunAgentInput

__all__ = ["AGUIEvent", "AGUIEventType", "RunAgentInput"]
