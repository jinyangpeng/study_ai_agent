"""智能体配置。

:class:`ModelConfig` 定义在 :mod:`src.providers.base`（属于
:class:`ChatModelBuilder` 协议的一部分），这里做 re-export 是为了让现有
调用方可以继续写 ``from src.core.config import ModelConfig``。

:class:`AgentConfig` 把每个注册供应商的 :class:`ModelConfig` 组合在一起，
外加一个 :attr:`strategy` 字段供 :class:`ModelFactory` 使用。

所有供应商的 ``base_url`` 默认值都从 :mod:`src.config.settings` 读
（环境变量 ``*_BASE_URL`` 可覆盖），由 :class:`BaseModelProvider` 子类在
构造 chat model 时按 ``config.base_url or settings.<X>_BASE_URL`` 解析。
"""

# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from src.config import settings
from src.providers.base import ModelConfig

__all__ = ["AgentConfig", "ModelConfig", "agent_config"]


class AgentConfig(BaseModel):
    """智能体配置。"""

    strategy: Literal["priority", "round_robin", "random"] = "priority"
    qianfan: ModelConfig = Field(default_factory=ModelConfig)
    zhipuai: ModelConfig = Field(default_factory=ModelConfig)
    deepseek: ModelConfig = Field(default_factory=ModelConfig)
    qwen: ModelConfig = Field(default_factory=ModelConfig)


agent_config = AgentConfig(
    strategy="priority",
    qianfan=ModelConfig(
        model_name="ernie-3.5-8k",
        priority=2,
        base_url=settings.QIANFAN_BASE_URL,
    ),
    zhipuai=ModelConfig(
        model_name="glm-5.1",
        priority=4,
        base_url=settings.ZAI_BASE_URL,
    ),
    #  zhipuai=ModelConfig(model_name="glm-4-flash", priority=1),
    deepseek=ModelConfig(
        model_name="deepseek-chat",
        priority=3,
        base_url=settings.DEEPSEEK_BASE_URL,
    ),
    # 注意：模型名必须在 DashScope OpenAI 兼容端点
    # （``https://dashscope.aliyuncs.com/compatible-mode/v1``）的可用列表里。
    # 早期版本填的是 ``qwen-math-turbo``（DashScope 原生 SDK 专用名），
    # 切到 OpenAI 兼容端点后会回 400 "model not found"。推荐用
    # ``qwen-turbo``（默认 / 免费档可访问）；想要更强推理可以选
    # ``qwen-plus`` / ``qwen-max``，但部分地域 / 套餐可能未开通。
    qwen=ModelConfig(
        model_name="qwen-flash",
        priority=1,
        base_url=settings.DASHSCOPE_BASE_URL,
    ),
)
