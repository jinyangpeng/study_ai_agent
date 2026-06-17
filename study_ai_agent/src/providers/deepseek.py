"""DeepSeek 供应商。

基于 ``langchain_deepseek`` 集成实现。``langchain_deepseek`` 内部用
``langchain_openai.ChatOpenAI`` 打 DeepSeek 端点，``base_url`` 默认就是
``https://api.deepseek.com``。这里把 ``base_url`` 暴露出来，方便企业
代理 / 跨地域场景覆盖（环境变量 ``DEEPSEEK_BASE_URL``）。
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

        kwargs: dict = dict(
            model=config.model_name or "deepseek-chat",
            api_key=settings.DEEPSEEK_API_KEY,
            streaming=True,
        )
        # 优先级：ModelConfig.base_url（程序覆盖） > settings 默认（环境变量）
        # 不传时由 langchain_deepseek 走内置默认
        base_url = config.base_url or settings.DEEPSEEK_BASE_URL
        if base_url:
            kwargs["base_url"] = base_url
        return ChatDeepSeek(**kwargs)


__all__ = ["DeepSeekProvider"]
