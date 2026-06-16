"""Smoke test for the post-refactor skeleton (2 skills)."""
import asyncio
import logging
import sys
from pathlib import Path

# Ensure the project root is importable so `from src.core import ...` works
# when this file is run directly with `python tests/manual/smoke_skeletons.py`.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
logging.disable(logging.CRITICAL)


def main() -> int:
    print("--- core imports ---")
    # Smoke-test these symbols are importable; ruff F401 is silenced.
    from src.core import (  # noqa: E402,F401
        AgentConfig,
        Citation,
        CodeChange,
        ModelConfig,
        ModelFactory,
        Plan,
        PlanStep,
        Review,
        SkillModule,
        model_factory,
    )
    print("[OK] core package exports")

    print("--- skills registry ---")
    from src.skills import DEFAULT_SKILL_ID, SKILL_REGISTRY  # noqa: E402,F401
    print(f"[OK] SKILL_REGISTRY: {sorted(SKILL_REGISTRY.keys())}")
    print(f"[OK] DEFAULT_SKILL_ID: {DEFAULT_SKILL_ID!r}")
    for sid, skill in SKILL_REGISTRY.items():
        print(
            f"  - {sid!r}: name={skill.name!r}, "
            f"tools={len(skill.tools)}, hitl_rules={len(skill.hitl_rules)}"
        )

    print("--- skill differences ---")
    coding = SKILL_REGISTRY["coding"]
    research = SKILL_REGISTRY["research"]
    print(f"  coding   tools: {sorted({t.name for t in coding.tools})}")
    print(f"  research tools: {sorted({t.name for t in research.tools})}")
    write_rule = coding.hitl_rules.get("write_file")
    print(f"  coding   hitl_rules[write_file]: {write_rule}")
    print(f"  research hitl_rules: {research.hitl_rules}")
    assert coding.hitl_rules, "coding should gate mutating tools"
    assert not research.hitl_rules, "research is read-only"

    print("--- core/tools + core/middleware ---")
    from src.core.middleware import ALL_MIDDLEWARES, BASE_MIDDLEWARES  # noqa: E402,F401
    from src.core.tools import ALL_TOOLS  # noqa: E402,F401
    print(f"[OK] ALL_TOOLS: {len(ALL_TOOLS)}")
    print(f"[OK] ALL_MIDDLEWARES: {len(ALL_MIDDLEWARES)} (placeholders + PII)")
    print(f"[OK] BASE_MIDDLEWARES: {len(BASE_MIDDLEWARES)} (HITL excluded by design)")

    print("--- skill-specific schemas ---")
    c = Citation(url="https://x.com", title="T", excerpt="E")
    print(f"[OK] Citation: {c.url}")
    ch = CodeChange(file="a.py", diff="+hello", description="added hello")
    print(f"[OK] CodeChange: {ch.file}")

    print("--- graph build ---")
    from src.core import graph as graph_module
    from src.core.graph import build_graph

    # 模型工厂在没有 API key 的开发环境下会爆。我们用 fake chat model 替换
    # ``model_factory.create_model``，这样图拓扑仍然可以验证、但不会真的
    # 调任何 LLM。
    class _FakeChatModel:
        """``BaseChatModel`` 的最小替身，足以喂给 ``create_agent`` 构造图。"""

        def __init__(self):
            pass

    async def compile_both():
        # 图编译时会 touch checkpointer_factory.saver，需要先 setup()。
        # 内存后端 setup 是同步的，postgres 后端需要 DB 在线 —— 用
        # ``CHECKPOINTER_BACKEND=memory`` 跑这个 smoke test 就行。
        from src.core.checkpointer import checkpointer_factory

        await checkpointer_factory.setup()
        try:
            # Monkey-patch：``create_model`` 在 ``graph.build_graph`` 调用时才查。
            original = graph_module.model_factory
            graph_module.model_factory = type(
                "FakeFactory", (), {"create_model": staticmethod(lambda _=None: (_FakeChatModel(), "fake"))}
            )()
            try:
                g_coding = build_graph(SKILL_REGISTRY["coding"])
                g_research = build_graph(SKILL_REGISTRY["research"])
            finally:
                graph_module.model_factory = original
            nodes_c = sorted(g_coding.get_graph().nodes.keys())
            nodes_r = sorted(g_research.get_graph().nodes.keys())
            print(f"  coding   graph nodes: {nodes_c}")
            print(f"  research graph nodes: {nodes_r}")
            # 不同的 skill 走不同策略 —— 拓扑不再要求一致。验证每个 skill
            # 确实走到自己声明的策略：coding=react、research=pera。
            expected_c = sorted(
                ["__start__", "react_agent", "act", "__end__"]
            )
            expected_r = sorted(
                ["__start__", "plan", "execute", "review", "act", "__end__"]
            )
            assert nodes_c == expected_c, (
                f"coding should use react topology, got {nodes_c}"
            )
            assert nodes_r == expected_r, (
                f"research should use p_e_r_a topology, got {nodes_r}"
            )
        finally:
            await checkpointer_factory.aclose()

    asyncio.run(compile_both())
    print("[OK] each skill compiles to its declared strategy topology")

    print("--- FastAPI app ---")
    import src.core.server as srv
    routes = sorted(
        [(r.path, ",".join(sorted(r.methods or []))) for r in srv.app.routes]
    )
    for path, methods in routes:
        print(f"  {methods:20s} {path}")
    assert any(p == "/skeletons" for p, _ in routes), "GET /skeletons must exist"
    assert any(p == "/health" for p, _ in routes), "GET /health must exist"
    assert any(p == "/" for p, _ in routes), "POST / must exist"
    print("[OK] all key endpoints present")

    print()
    print("=== ALL SMOKE TESTS PASSED ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
