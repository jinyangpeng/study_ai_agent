"""智谱 AI / Z.ai（GLM）供应商。

走智谱的 **OpenAI 兼容端点**，使用 ``langchain_openai.ChatOpenAI``。
**不**使用 ``langchain_community.chat_models.zhipuai.ChatZhipuAI``（官方
sunset + 自己实现了一层不完整的 OpenAI 协议，不支持 ``tool_choice="any"``）。

官方示例：

.. code-block:: python

    llm = ChatOpenAI(
        temperature=0.6,
        model="glm-5.1",
        openai_api_key="...",
        openai_api_base="https://open.bigmodel.cn/api/paas/v4/",
    )

``base_url`` 可被环境变量 ``ZAI_BASE_URL`` 覆盖，方便走企业代理。
"""

# -*- coding: utf-8 -*-
from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from src.config import settings
from src.providers.base import BaseModelProvider, ModelConfig


class ZhipuAIProvider(BaseModelProvider):
    """智谱 AI / Z.ai（GLM）供应商（OpenAI 兼容端点）。

    通过 OpenAI 兼容协议打智谱官方端点，自动获得：
    * 完整的 ``tool_choice`` 支持（``"auto"`` / ``"any"`` / 字典形式）
    * 函数调用 / structured output
    * 系统代理透传（``langchain_openai`` 内部 httpx 默认 ``trust_env=True``）
    * 流式 / 异步 / 重试逻辑
    """

    def build_chat(self, config: ModelConfig) -> BaseChatModel:
        if not settings.ZAI_API_KEY:
            raise ValueError("ZAI_API_KEY not set")
        return ChatOpenAI(
            model=config.model_name or "glm-5.1",
            api_key=settings.ZAI_API_KEY,
            # 优先级：ModelConfig.base_url（程序覆盖） > settings 默认（环境变量）
            base_url=config.base_url or settings.ZAI_BASE_URL,
            streaming=True,
        )


__all__ = ["ZhipuAIProvider"]
