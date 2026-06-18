"""E2E test: real create_agent + ainvoke, with PII."""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from src.core.middleware import BASE_MIDDLEWARES


async def main():
    # Fake model: 直接回显用户消息
    fake = FakeListChatModel(responses=["echoed: {messages}"])
    agent = create_agent(model=fake, middleware=BASE_MIDDLEWARES)

    text = "请帮我发邮件给 test@test.com, 问他好"
    print(f"in  : {text!r}")
    result = await agent.ainvoke({"messages": [HumanMessage(content=text)]})
    last = result["messages"][-1]
    print(f"out : {last.content!r}")
    # 检查 state 里 PII 是否被改写过
    for i, m in enumerate(result["messages"]):
        if isinstance(m, HumanMessage):
            print(f"  msg[{i}] (HumanMessage): {m.content!r}")
        else:
            content = getattr(m, "content", "")
            print(f"  msg[{i}] ({type(m).__name__}): {str(content)[:100]!r}")

asyncio.run(main())