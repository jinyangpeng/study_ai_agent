"""技能 / 智能体注册表。

新加一个智能体只需要在这里 append 一行。新 skill 会被自动加入
:data:`SKILL_REGISTRY`，然后通过 :mod:`src.core.server` 的 ``/skeletons``
端点暴露给 AG-UI 前端。

设置默认智能体
--------------
:data:`DEFAULT_SKILL_ID` 决定用户没在 AG-UI 选择器里挑智能体时使用哪个。
当前选 ``"research"``，因为它无副作用（不需要审批），适合作为起步 /
教学场景。
"""
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.skill import SkillModule


# 直接 import 而不是懒加载 —— registry 在 :mod:`src.core.server` 的请求时
# 才查，import 期间的额外开销可以接受。
from src.skills.coding import CodingSkill
from src.skills.research import ResearchSkill

# 显式声明注册表（不是自动 importlib），这样新加智能体时一目了然。
SKILL_REGISTRY: dict[str, "SkillModule"] = {
    "coding": CodingSkill(),
    "research": ResearchSkill(),
}

# 没有 ``forwarded_props.skill`` 时使用哪个。
DEFAULT_SKILL_ID = "research"

__all__ = ["SKILL_REGISTRY", "DEFAULT_SKILL_ID"]
