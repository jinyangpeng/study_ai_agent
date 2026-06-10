"""核心包：所有智能体（skill）共用的内核。

re-export 一些最常用的符号，调用方可以直接写::

    from src.core import Plan, Review, AgentState, model_factory, SkillModule

而不用进入各个子模块。
"""
# -*- coding: utf-8 -*-
from __future__ import annotations

from src.core.config import AgentConfig, ModelConfig, agent_config
from src.core.events import AGUIEvent, AGUIEventType, RunAgentInput
from src.core.model_factory import ModelFactory, model_factory
from src.core.schemas import Citation, CodeChange, Plan, PlanStep, Review
from src.core.skill import SkillModule
from src.core.state import AgentState

__all__ = [
    # Pydantic 模型
    "Plan",
    "PlanStep",
    "Review",
    "Citation",
    "CodeChange",
    # LangGraph state
    "AgentState",
    # 插件契约
    "SkillModule",
    # AG-UI 协议类型
    "AGUIEvent",
    "AGUIEventType",
    "RunAgentInput",
    # 模型工厂
    "ModelFactory",
    "model_factory",
    # 配置
    "AgentConfig",
    "ModelConfig",
    "agent_config",
]
