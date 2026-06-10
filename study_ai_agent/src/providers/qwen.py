"""阿里通义千问 / DashScope 供应商。

基于 ``langchain_community`` 的 Tongyi 集成。wrapper 开启 streaming，
让 AG-UI 事件流可以逐块看到模型输出，而不是一次性拿到完整响应。
"""
# -*- coding: utf-8 -*-
from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from src.config import settings
from src.providers.base import BaseModelProvider, ModelConfig


class QwenProvider(BaseModelProvider):
    """阿里通义千问 / Tongyi chat 模型。

    类本身就实现了 :class:`ChatModelBuilder`；按需实例化（这些供应商
    是无状态的）。
    """

    def build_chat(self, config: ModelConfig) -> BaseChatModel:
        if not settings.DASHSCOPE_API_KEY:
            raise ValueError("DASHSCOPE_API_KEY not set")
        from langchain_community.chat_models.tongyi import ChatTongyi

        return ChatTongyi(
            model=config.model_name or "qwen-turbo",
            dashscope_api_key=settings.DASHSCOPE_API_KEY,
            streaming=True,
        )


__all__ = ["QwenProvider"]
