"""百度千帆（ERNIE）供应商。

使用百度千帆 v2 暴露的 OpenAI 兼容端点，这样我们可以复用
``langchain_openai.ChatOpenAI`` 的标准流式输出和 tool calling 能力。
"""
# -*- coding: utf-8 -*-
from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from src.config import settings
from src.providers.base import BaseModelProvider, ModelConfig


class QianfanProvider(BaseModelProvider):
    """百度千帆 chat 模型（ERNIE 系列）。

    类本身就实现了 :class:`ChatModelBuilder`；按需实例化（这些供应商
    是无状态的）。
    """

    def build_chat(self, config: ModelConfig) -> BaseChatModel:
        if not settings.QIANFAN_API_KEY:
            raise ValueError("QIANFAN_API_KEY not set")
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=config.model_name or "ernie-3.5-8k",
            api_key=settings.QIANFAN_API_KEY,
            base_url=config.base_url or "https://qianfan.baidubce.com/v2",
            streaming=True,
        )


__all__ = ["QianfanProvider"]
