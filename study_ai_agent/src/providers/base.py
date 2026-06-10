"""供应商基类 - 各家厂商的 chat-model 工厂。

子类实现 ``build_chat(config) -> BaseChatModel``。``config`` 是此处定义的
per-provider :class:`ModelConfig`，所以同一个 wrapper 既可以直接用（单厂商
agent），也可以走 :class:`ModelFactory`（自动选供应商）。

本模块是 :class:`ModelConfig` 的唯一权威定义。位于智能体层的
:class:`AgentConfig`（在 :mod:`src.core.config`）对其做了 re-export，
方便 ``from src.core.config import ModelConfig`` 这种写法。
"""
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Protocol

from pydantic import BaseModel

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel


class ModelConfig(BaseModel):
    """per-provider 的模型配置。

    故意保持最小：模型名、用于选择的 priority、可选的厂商 base_url 覆盖。
    """

    model_name: str = ""
    priority: int = 0
    base_url: Optional[str] = None


class ChatModelBuilder(Protocol):
    """每个供应商 wrapper 必须满足的协议。"""

    def build_chat(self, config: "ModelConfig") -> "BaseChatModel":
        """使用给定的 per-provider config 构造一个 chat model。"""
        ...


class BaseModelProvider:
    """便捷基类 - 子类只需要实现 :meth:`build_chat`。

    类本身就实现了 :class:`ChatModelBuilder`；子类无状态，使用方按需实例化
    而不依赖模块级单例（否则 ``from src.providers import <name>`` 时会与
    子模块名冲突）。
    """

    def build_chat(self, config: "ModelConfig") -> "BaseChatModel":
        raise NotImplementedError("Subclasses must implement build_chat(config)")


__all__ = ["BaseModelProvider", "ChatModelBuilder", "ModelConfig"]
