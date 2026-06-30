"""模型工厂 - 自动选择供应商。

工厂负责决定 agent 用哪家供应商（priority / round_robin / random），
取对应的 per-vendor :class:`ModelConfig`，再把模型构造委托给
``src.providers`` 中对应的 wrapper 类。这是供应商选择的唯一决策点，
wrapper 本身不关心策略。

供应商类是无状态的，所以注册表存的是 **类**（不是预先实例化的单例），
``create_model`` 按需实例化。这样可以避免 ``from src.providers import
qianfan`` 返回 *子模块* 而非单例的命名冲突。
"""

# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import random
from typing import Optional, Type

from langchain_core.language_models.chat_models import BaseChatModel

from src.config import settings
from src.core.config import AgentConfig, agent_config
from src.providers import (
    ChatModelBuilder,
    DeepSeekProvider,
    ModelConfig,
    QianfanProvider,
    QwenProvider,
    ZhipuAIProvider,
)

logger = logging.getLogger(__name__)


# 供应商名 -> (供应商类, 要检查的 settings key)。
# key 必须和 `AgentConfig` 的字段、`src.config.settings` 保持一致。
_PROVIDER_REGISTRY: dict[str, tuple[Type[ChatModelBuilder], str]] = {
    "qianfan": (QianfanProvider, "QIANFAN_API_KEY"),
    "zhipuai": (ZhipuAIProvider, "ZAI_API_KEY"),
    "deepseek": (DeepSeekProvider, "DEEPSEEK_API_KEY"),
    "qwen": (QwenProvider, "DASHSCOPE_API_KEY"),
}


class ModelFactory:
    """按配置的策略选供应商，返回可用的 chat model。"""

    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or agent_config
        self._round_robin_index = 0
        self._available_providers: list[str] = self._detect_available_providers()

    def _detect_available_providers(self) -> list[str]:
        """只保留实际配置了 API key 的供应商。"""
        available: list[str] = []
        for name, (_cls, settings_key) in _PROVIDER_REGISTRY.items():
            if getattr(settings, settings_key, ""):
                available.append(name)
                logger.info("%s API key configured, available", name.upper())
            else:
                logger.warning("%s API key not configured, unavailable", name.upper())
        if not available:
            logger.error("No available model providers! Please configure at least one API key.")
        return available

    def _select_provider(self) -> Optional[str]:
        """按 ``self.config.strategy`` 挑一个供应商。"""
        if not self._available_providers:
            return None
        strategy = self.config.strategy
        if strategy == "round_robin":
            provider = self._available_providers[self._round_robin_index % len(self._available_providers)]
            self._round_robin_index += 1
            return provider
        if strategy == "random":
            return random.choice(self._available_providers)
        # 默认：priority（数字小的胜出）
        return sorted(self._available_providers, key=self._priority_for)[0]

    def _priority_for(self, provider: str) -> int:
        cfg: ModelConfig = getattr(self.config, provider, ModelConfig())
        return cfg.priority

    def create_model(self, provider: Optional[str] = None) -> tuple[BaseChatModel, str]:
        """用选中的（或自动选的）供应商构造一个 chat model。

        返回:
            ``(model, provider_name)`` 元组。

        #27 max_tokens：若 ``settings.MODEL_MAX_TOKENS > 0``，用
        ``model.bind(max_tokens=...)`` 给每次 LLM 调用加输出上限，防生成
        过长导致响应慢 / 成本失控。返回的是 ``RunnableBinding``，对调用方
        透明（同样支持 ``ainvoke`` / ``stream`` 等）。
        """
        selected = provider or self._select_provider()
        if selected is None:
            raise ValueError("No available model providers configured")
        if selected not in _PROVIDER_REGISTRY:
            raise ValueError(f"Unknown provider: {selected}")

        provider_cls, _key = _PROVIDER_REGISTRY[selected]
        config = getattr(self.config, selected, ModelConfig())
        model = provider_cls().build_chat(config)

        # #27 max_tokens：防 LLM 生成过长
        max_tokens = settings.MODEL_MAX_TOKENS
        if max_tokens and max_tokens > 0:
            try:
                model = model.bind(max_tokens=max_tokens)
                logger.info("Model bound with max_tokens=%d", max_tokens)
            except (TypeError, ValueError) as exc:
                # 某些 provider 可能不支持 max_tokens 参数，降级为不绑定
                logger.warning("bind(max_tokens=%d) 失败，跳过: %s", max_tokens, exc)

        return model, selected


model_factory = ModelFactory()
