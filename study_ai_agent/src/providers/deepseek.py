"""DeepSeek 供应商。

基于 ``langchain_deepseek`` 集成实现。wrapper 尽量保持薄，让项目其它部分
（agent 构建、:class:`ModelFactory`、测试）能把它当作普通的
:class:`BaseChatModel` 来对待。
"""
# -*- coding: utf-8 -*-
from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from src.config import settings
from src.providers.base import BaseModelProvider, ModelConfig


class DeepSeekProvider(BaseModelProvider):
    """DeepSeek chat 模型（deepseek-chat、deepseek-coder 等）。

    类本身就实现了 :class:`ChatModelBuilder`；按需实例化（这些供应商
    是无状态的）。
    """

    def build_chat(self, config: ModelConfig) -> BaseChatModel:
        if not settings.DEEPSEEK_API_KEY:
            raise ValueError("DEEPSEEK_API_KEY not set")
        from langchain_deepseek import ChatDeepSeek

        return ChatDeepSeek(
            model=config.model_name or "deepseek-chat",
            api_key=settings.DEEPSEEK_API_KEY,
            streaming=True,
        )


__all__ = ["DeepSeekProvider"]
