"""smoke：三个策略 (p_e_r_a / react / reflection) 都能编译 + 节点拓扑正确。

跑法（项目根）::

    $env:CHECKPOINTER_BACKEND="memory"
    .\\venv\\Scripts\\python.exe tests\\manual\\smoke_strategies.py

只验图编译 / 拓扑，不发真实 LLM 请求 —— ``model_factory`` 在没配 LLM
key 时会抛错，所以这里 monkeypatch 一个假 model。
"""
# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import logging
import sys
import traceback
from pathlib import Path
from typing import Any

# Ensure the project root is importable so `from src.core import ...` works
# when this file is run directly with `python tests/manual/smoke_strategies.py`.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
logging.disable(logging.CRITICAL)


# ---------------------------------------------------------------------------
# 假 model —— 任何 ``ainvoke`` / ``invoke`` 都给空 messages
# ---------------------------------------------------------------------------
class _FakeChatModel:
    """``BaseChatModel`` 的最小替身，足以喂给 ``create_agent`` 构造图。"""

    def __init__(self) -> None:
        pass


# ---------------------------------------------------------------------------
# 核心 smoke
# ---------------------------------------------------------------------------
def _patch_model_factory(monkey) -> None:
    """把 ``model_factory.create_model`` 替换成返回假 model。"""
    from src.core import model_factory

    def _fake_create_model(*args: Any, **kwargs: Any):
        return _FakeChatModel(), "fake"

    monkey.setattr(model_factory, "create_model", _fake_create_model)


def _check_strategy(name: str) -> None:
    """按名取策略，验证名字 + 类归属。"""
    from src.core.strategies import get, available

    assert name in available(), f"{name!r} not in registry: {available()}"
    s = get(name)
    assert s.name == name, f"name mismatch: {s.name} != {name}"
    print(f"[OK] strategy registered: {name} -> {type(s).__name__}")


async def _build_for_skill(strategy_name: str, skill_id: str) -> list[str]:
    """用给定策略编译图，返回业务节点列表。"""
    from src.core.graph import build_graph
    from src.skills import SKILL_REGISTRY

    skill = SKILL_REGISTRY[skill_id]
    g = build_graph(skill, strategy_name=strategy_name)
    # 节点排序：``__start__`` / ``__end__`` 跳过，只看业务节点
    nodes = sorted(
        n for n in g.get_graph().nodes.keys() if not n.startswith("__")
    )
    return nodes


async def main_async() -> int:
    from _pytest.monkeypatch import MonkeyPatch  # type: ignore
    monkey = MonkeyPatch()
    try:
        _patch_model_factory(monkey)

        # 图编译会 touch checkpointer_factory.saver，需要先 setup()。
        # 内存后端 setup 是同步的；postgres 后端需要 DB 在线 —— 用
        # ``CHECKPOINTER_BACKEND=memory`` 跑这个 smoke test 就行。
        from src.core.checkpointer import checkpointer_factory
        await checkpointer_factory.setup()

        # ---- 三个策略都注册了 ----
        from src.core.strategies import available
        print("--- registry ---")
        print(f"[OK] available strategies: {available()}")
        for name in ("p_e_r_a", "react", "reflection"):
            _check_strategy(name)

        # ---- 每个策略都能编译出图（业务节点集合） ----
        print("\n--- graph build ---")
        expected = {
            "p_e_r_a": {"plan", "execute", "review", "act"},
            "react": {"react_agent", "act"},
            "reflection": {"generate", "critique", "refine", "act"},
        }
        for strat in ("p_e_r_a", "react", "reflection"):
            nodes = await _build_for_skill(strat, "qa")
            assert expected[strat] == set(nodes), (
                f"{strat}: expected {expected[strat]}, got {set(nodes)}"
            )
            print(f"  {strat:<11} qa nodes: {nodes}")

        # ---- 换 skill 也能编译（说明策略不绑死 skill） ----
        print("\n--- different skill ---")
        for skill_id in ("coding", "research", "qa"):
            nodes = await _build_for_skill("reflection", skill_id)
            assert nodes == ["act", "critique", "generate", "refine"], nodes
            print(f"  reflection + {skill_id:<8} nodes: {nodes}")

        # ---- Reflection 路由函数存在 ----
        print("\n--- reflection routing ---")
        from src.core.strategies.reflection import should_refine
        from src.core.schemas import Critique
        state_approve = {"critique": Critique(verdict="approve")}
        state_revise = {"critique": Critique(verdict="revise", issues=["x"])}
        assert should_refine(state_approve) == "act"
        assert should_refine(state_revise) == "refine"
        print("[OK] should_refine(approve) -> act")
        print("[OK] should_refine(revise) -> refine")

        print("\n[ALL OK] three strategies compile and route correctly.")
        return 0
    except Exception:
        traceback.print_exc()
        return 1
    finally:
        monkey.undo()
        try:
            await checkpointer_factory.aclose()
        except Exception:
            pass


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(main())
