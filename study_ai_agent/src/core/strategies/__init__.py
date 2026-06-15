"""推理策略注册表 —— 全局唯一入口。

用法
====

* **取实例**：:func:`get` 拿策略实例，按 ``skill.strategy`` 或 settings 选择。
* **注册新策略**：装饰 :class:`BaseStrategy` 子类即可，外部模块
  （含 skill 包）可在自己 import 时把自己注册进来。

::

    # 核心内置策略 —— 在这里 import + register
    from src.core.strategies.p_e_r_a import PerAStrategy
    from src.core.strategies import register
    register(PerAStrategy)

    # 业务侧自定义
    @register
    class MyCustomStrategy(BaseStrategy):
        name = "custom"
        ...

注意：注册时校验 ``name`` 非空，否则直接抛 :class:`ValueError`，避免
后来用空 key 静默查不到。
"""
# -*- coding: utf-8 -*-
from __future__ import annotations

from src.core.strategies.base import BaseStrategy, NodeFn, extract_structured
from src.core.strategies.p_e_r_a import PerAStrategy

__all__ = [
    "BaseStrategy",
    "NodeFn",
    "PerAStrategy",
    "extract_structured",
    "get",
    "register",
]


# ---------------------------------------------------------------------------
# 全局注册表
# ---------------------------------------------------------------------------
_REGISTRY: dict[str, type[BaseStrategy]] = {}


def register(cls: type[BaseStrategy]) -> type[BaseStrategy]:
    """类装饰器：把策略注册到全局表。

    重复注册同一 name 会被覆盖（最后一个生效），方便测试场景下替换
    默认实现；生产代码应当在 import 时一次性完成注册。
    """
    if not cls.name:
        raise ValueError(
            f"{cls.__name__}.name 不能为空字符串，注册前请显式赋值。"
        )
    if not issubclass(cls, BaseStrategy):
        raise TypeError(f"{cls.__name__} 必须继承 BaseStrategy")
    _REGISTRY[cls.name] = cls
    return cls


def get(name: str) -> BaseStrategy:
    """按名取策略实例。找不到时抛 :class:`ValueError` 并列出可用项。"""
    cls = _REGISTRY.get(name)
    if cls is None:
        available = ", ".join(sorted(_REGISTRY)) or "<empty>"
        raise ValueError(
            f"未知的推理策略: {name!r}。可用策略: {available}"
        )
    return cls()


def available() -> list[str]:
    """列出已注册的全部策略名。供 /health 端点 / 调试用。"""
    return sorted(_REGISTRY)


# ---------------------------------------------------------------------------
# 注册内置策略
# ---------------------------------------------------------------------------
# 这一行必须在文件最末尾执行（确保所有策略类已 import）。
# 后续要加 ReAct / Reflection 时，把它们的 import 放在这里并 ``register(Cls)`` 即可。
for _cls in (PerAStrategy,):
    register(_cls)
