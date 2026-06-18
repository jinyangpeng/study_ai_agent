"""Verify PII middleware is now wired into p_e_r_a and reflection strategies."""
import sys, asyncio
sys.path.insert(0, ".")
from langchain_core.messages import HumanMessage
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from src.skills import SKILL_REGISTRY
from src.core.strategies.p_e_r_a import PerAStrategy
from src.core.strategies.reflection import ReflectionStrategy


def list_middlewares(agent):
    """Extract middleware list from create_agent result."""
    return getattr(agent, "middleware", None) or getattr(agent, "_middlewares", None)


async def test_p_e_r_a():
    print("--- p_e_r_a strategy ---")
    skill = SKILL_REGISTRY["research"]
    fake = FakeListChatModel(responses=["ok"] * 200)
    strat = PerAStrategy()
    # _make_plan_node / _make_review_node / _make_execute_node 都用 closure 返回 node fn
    # 但要拿 agent 实例, 我们手动调 _make_*
    plan_node = PerAStrategy._make_plan_node(skill, fake)
    execute_node = PerAStrategy._make_execute_node(skill, fake)
    review_node = PerAStrategy._make_review_node(skill, fake)
    # 跑一遍 plan node 看 state.messages 是否被脱敏
    text = "帮我发一份email给test@test.com，帮我向他问好并祝他生日快乐。"
    state = {"messages": [HumanMessage(content=text)]}
    result = await plan_node(state)
    msgs = result.get("messages", [])
    print(f"  plan_node output messages:")
    for m in msgs[:3]:
        c = m.content if isinstance(m.content, str) else str(m.content)
        print(f"    {c[:120]!r}")
    # 判断
    raw = "test@test.com" in " ".join(str(m.content) for m in msgs)
    red = "[REDACTED_EMAIL]" in " ".join(str(m.content) for m in msgs)
    print(f"  raw in output: {raw}, redacted in output: {red}")
    print(f"  => {'OK' if (not raw and red) else 'FAIL'}")
    print()


async def test_reflection():
    print("--- reflection strategy ---")
    skill = SKILL_REGISTRY["research"]
    fake = FakeListChatModel(responses=["ok"] * 200)
    # generate_node 已带 middleware, 我们跑 critique_node 验证新加的
    critique_node = ReflectionStrategy._make_critique_node(skill, fake)
    text = "Current draft to improve: test@test.com, please help rewrite without exposing the email."
    state = {"messages": [HumanMessage(content=text)]}
    result = await critique_node(state)
    msgs = result.get("messages", [])
    print(f"  critique_node output messages:")
    for m in msgs[:3]:
        c = m.content if isinstance(m.content, str) else str(m.content)
        print(f"    {c[:120]!r}")
    raw = "test@test.com" in " ".join(str(m.content) for m in msgs)
    red = "[REDACTED_EMAIL]" in " ".join(str(m.content) for m in msgs)
    print(f"  raw in output: {raw}, redacted in output: {red}")
    print(f"  => {'OK' if (not raw and red) else 'FAIL'}")


async def main():
    await test_p_e_r_a()
    await test_reflection()


asyncio.run(main())