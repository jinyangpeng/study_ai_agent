"""阿里通义千问 / DashScope 供应商。

走 DashScope 的 **OpenAI 兼容端点**，使用 ``langchain_openai.ChatOpenAI``：

* 不再依赖 ``langchain_community.chat_models.tongyi``（即 ``dashscope`` SDK）
* 自动获得完整的 ``tool_choice`` / 函数调用 / structured output 支持
* streaming / 异步 / 重试逻辑统一由 ``langchain_openai`` 提供
* ``base_url`` 可被环境变量 ``DASHSCOPE_BASE_URL`` 覆盖，方便企业代理 / 跨地域

参考阿里云百炼文档：
https://help.aliyun.com/model-studio/developer-reference/use-qwen-by-calling-api
"""
# -*- coding: utf-8 -*-
from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from src.config import settings
from src.providers.base import BaseModelProvider, ModelConfig


class QwenProvider(BaseModelProvider):
    """阿里通义千问 / Tongyi chat 模型（OpenAI 兼容端点）。"""

    def build_chat(self, config: ModelConfig) -> BaseChatModel:
        if not settings.DASHSCOPE_API_KEY:
            raise ValueError("DASHSCOPE_API_KEY not set")
        return ChatOpenAI(
            # 默认 ``qwen-turbo`` 兼容 DashScope 兼容端点的可用列表。
            # 想要更强推理可手动传 ``qwen-plus`` / ``qwen-max``。
            model=config.model_name or "qwen-plus-2025-07-14",
            api_key=settings.DASHSCOPE_API_KEY,
            # 优先级：ModelConfig.base_url（程序覆盖） > settings 默认（环境变量）
            base_url=config.base_url or settings.DASHSCOPE_BASE_URL,
            streaming=True,
        )


__all__ = ["QwenProvider"]
