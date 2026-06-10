"""智能体配置。

:class:`ModelConfig` 定义在 :mod:`src.providers.base`（属于
:class:`ChatModelBuilder` 协议的一部分），这里做 re-export 是为了让现有
调用方可以继续写 ``from src.core.config import ModelConfig``。

:class:`AgentConfig` 把每个注册供应商的 :class:`ModelConfig` 组合在一起，
外加一个 :attr:`strategy` 字段供 :class:`ModelFactory` 使用。
"""
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

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
        base_url="https://qianfan.baidubce.com/v2",
    ),
    zhipuai=ModelConfig(model_name="glm-5.1", priority=1),
    #  zhipuai=ModelConfig(model_name="glm-4-flash", priority=1),
    deepseek=ModelConfig(model_name="deepseek-chat", priority=3),
    qwen=ModelConfig(model_name="qwen-turbo", priority=4),
)
