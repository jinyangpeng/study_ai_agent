"""智谱 AI（GLM）供应商的集成测试。

测试目标
--------
* :class:`src.providers.zhipuai.ZhipuAIProvider` 工厂能正确产出可用的 chat model
* 流式 / 非流式调用都通
* 当 :envvar:`ZAI_API_KEY` 缺失时，:meth:`build_chat` 主动抛错（fail-fast）

运行
----
需要 ``.env`` 中有可用的 ``ZAI_API_KEY``：

.. code-block:: bash

    pytest tests/llm/test_zhipuai.py -v

无 key 时所有联网 case 会被 ``pytest.skip`` 跳过，只跑本地构建测试。
"""
# -*- coding: utf-8 -*-
from __future__ import annotations

import os

import pytest
from langchain_core.messages import HumanMessage

from src.config import settings
from src.providers import ModelConfig, ZhipuAIProvider


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def provider() -> ZhipuAIProvider:
    """一个无状态 provider 实例，按需实例化符合协议。"""
    return ZhipuAIProvider()


@pytest.fixture
def default_config() -> ModelConfig:
    """项目内置的 zhipuai 默认配置（模型名 = ``glm-4-flash``）。"""
    from src.core.config import agent_config

    return agent_config.zhipuai


@pytest.fixture
def zhipu_api_key() -> str | None:
    """``ZAI_API_KEY``，无 key 时为 ``None``。"""
    return settings.ZAI_API_KEY or os.getenv("ZAI_API_KEY") or None


# ---------------------------------------------------------------------------
# 本地构建测试（不需要网络）
# ---------------------------------------------------------------------------
class TestBuildChatLocal:
    """``build_chat`` 的纯本地逻辑：参数映射、缺 key 时的 fail-fast。"""

    def test_缺_api_key_应抛_value_error(self, provider: ZhipuAIProvider, monkeypatch):
        """没配置 ZAI_API_KEY 时必须显式报错，而不是带着空 key 调远端。"""
        monkeypatch.setattr(settings, "ZAI_API_KEY", "")
        with pytest.raises(ValueError, match="ZAI_API_KEY"):
            provider.build_chat(ModelConfig(model_name="glm-4-flash"))

    def test_使用_config_中的_model_name(
        self, provider: ZhipuAIProvider, default_config: ModelConfig, zhipu_api_key: str | None
    ):
        """``config.model_name`` 应该原样传给底层 chat model。"""
        if not zhipu_api_key:
            pytest.skip("ZAI_API_KEY not configured")
        chat = provider.build_chat(default_config)
        # ``ChatOpenAI``（langchain_openai）的字段就是 ``model_name``
        assert chat.model_name == default_config.model_name

    def test_默认_开启流式(
        self, provider: ZhipuAIProvider, default_config: ModelConfig, zhipu_api_key: str | None
    ):
        """项目里 zhipuai provider 强制 streaming=True，断言一下不要被无意改回 False。"""
        if not zhipu_api_key:
            pytest.skip("ZAI_API_KEY not configured")
        chat = provider.build_chat(default_config)
        assert chat.streaming is True

    def test_返回_BaseChatModel_实例(
        self, provider: ZhipuAIProvider, default_config: ModelConfig, zhipu_api_key: str | None
    ):
        """返回值类型必须是 ``BaseChatModel``，符合 :class:`ChatModelBuilder` 协议。"""
        from langchain_core.language_models.chat_models import BaseChatModel

        if not zhipu_api_key:
            pytest.skip("ZAI_API_KEY not configured")
        chat = provider.build_chat(default_config)
        assert isinstance(chat, BaseChatModel)


# ---------------------------------------------------------------------------
# 联网测试
# ---------------------------------------------------------------------------
class TestZhipuChatLive:
    """真实打智谱 API 的端到端测试。"""

    @pytest.mark.asyncio
    async def test_非流式聊天(
        self, provider: ZhipuAIProvider, default_config: ModelConfig, zhipu_api_key: str | None
    ):
        """``ainvoke`` 一次普通对话，能拿到非空字符串回复。"""
        if not zhipu_api_key:
            pytest.skip("ZAI_API_KEY not configured")
        chat = provider.build_chat(default_config)
        result = await chat.ainvoke([HumanMessage(content="用一句话说 OK")])
        print("DEBUG:", repr(result.content))
        # 智谱有概率返回中文"好的"之类的词；这里只断言"有内容"
        assert isinstance(result.content, str)
        assert result.content.strip(), "模型返回了空字符串"

    @pytest.mark.asyncio
    async def test_流式聊天(
        self, provider: ZhipuAIProvider, default_config: ModelConfig, zhipu_api_key: str | None
    ):
        """``astream`` 能逐 token 推进，累积内容非空。"""
        if not zhipu_api_key:
            pytest.skip("ZAI_API_KEY not configured")
        chat = provider.build_chat(default_config)
        chunks: list[str] = []
        async for chunk in chat.astream([HumanMessage(content="1+1 等于几？一个数字回答")]):
            chunks.append(chunk.content if isinstance(chunk.content, str) else "")
        full = "".join(chunks)
        assert full.strip(), "流式累积内容为空"
        # 至少要能拿到一个数字字符
        assert any(ch.isdigit() for ch in full), f"流式回复里没数字: {full!r}"


# ---------------------------------------------------------------------------
# smoke：和 ``ModelFactory`` 协作
# ---------------------------------------------------------------------------
def test_model_factory_能挑到_zhipuai(monkeypatch):
    """在只配 zhipuai key 的情况下，``ModelFactory`` 应当把它选上。"""
    from src.core.model_factory import ModelFactory

    # 把其他三家的 key 都清空，强制只选 zhipuai
    from src.config import settings

    for attr in ("QIANFAN_API_KEY", "DEEPSEEK_API_KEY", "DASHSCOPE_API_KEY"):
        monkeypatch.setattr(settings, attr, "")
    if not settings.ZAI_API_KEY:
        pytest.skip("ZAI_API_KEY not configured")
    factory = ModelFactory()
    assert "zhipuai" in factory._available_providers
    # priority=2 在 priority 体系下被排到第一个（其它都被剔除了）
    assert factory._select_provider() == "zhipuai"
