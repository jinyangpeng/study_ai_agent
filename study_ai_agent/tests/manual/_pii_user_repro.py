"""Reproduce user reported issue: PII not redacted for test@test.com"""
import asyncio, sys
sys.path.insert(0, ".")
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from src.core.middleware import BASE_MIDDLEWARES


async def main():
    fake = FakeListChatModel(responses=["ok"] * 100)
    agent = create_agent(model=fake, middleware=BASE_MIDDLEWARES)
    # Exactly the user's wording
    text = "帮我发一份email给test@test.com，帮我向他问好并祝他生日快乐。"
    print(f"USER INPUT (raw)        : {text!r}")
    result = await agent.ainvoke({"messages": [HumanMessage(content=text)]})
    print()
    print("--- state.messages after ainvoke ---")
    for i, m in enumerate(result["messages"]):
        c = m.content if isinstance(m.content, str) else str(m.content)
        print(f"  msg[{i}] {type(m).__name__:14s}: {c[:200]!r}")
    print()
    # Check if PII was redacted in the final state
    raw_text = "".join(
        m.content if isinstance(m.content, str) else str(m.content)
        for m in result["messages"]
    )
    if "test@test.com" in raw_text:
        print("[FAIL] test@test.com still in state.messages")
    else:
        print("[OK]   test@test.com redacted in state.messages")
    if "[REDACTED_EMAIL]" in raw_text:
        print("[OK]   [REDACTED_EMAIL] present in state.messages")
    else:
        print("[FAIL] [REDACTED_EMAIL] NOT in state.messages")


asyncio.run(main())