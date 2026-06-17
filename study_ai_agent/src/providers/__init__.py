"""Provider registry - per-vendor chat-model factories.

Each submodule exposes a `*Provider` class that implements the
`ChatModelBuilder` protocol (via the shared `BaseModelProvider`). The
classes are stateless, so consumers instantiate them on demand (e.g.
`ModelFactory.create_model`).

Public API
----------
    from src.providers import QianfanProvider, ZhipuAIProvider, ...
    from src.providers import ModelConfig, ChatModelBuilder, BaseModelProvider
"""

# -*- coding: utf-8 -*-
from __future__ import annotations

from src.providers.base import BaseModelProvider, ChatModelBuilder, ModelConfig
from src.providers.deepseek import DeepSeekProvider
from src.providers.qianfan import QianfanProvider
from src.providers.qwen import QwenProvider
from src.providers.zhipuai import ZhipuAIProvider

__all__ = [
    "BaseModelProvider",
    "ChatModelBuilder",
    "DeepSeekProvider",
    "ModelConfig",
    "QianfanProvider",
    "QwenProvider",
    "ZhipuAIProvider",
]
