"""PII e2e via real skill + agent + ainvoke."""
import asyncio, sys
sys.path.insert(0, ".")
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from src.core.middleware import BASE_MIDDLEWARES
from src.core.server import _compiled_graph_for, _default_skill_id
from src.core.checkpointer import checkpointer_factory


async def main():
    await checkpointer_factory.setup()
    skill_id = _default_skill_id()
    skill, _graph = _compiled_graph_for(skill_id)
    print("skill:", skill_id, "strategy:", skill.strategy)
    fake = FakeListChatModel(responses=["ok"] * 100)
    agent = create_agent(
        model=fake,
        tools=list(skill.tools),
        middleware=BASE_MIDDLEWARES,
        system_prompt=getattr(skill, "react_prompt", None) or getattr(skill, "system_prompt", None) or "you are an assistant",
    )
    text = "请帮我发邮件给 test@test.com, 问他好"
    result = await agent.ainvoke({"messages": [HumanMessage(content=text)]})
    print("--- after agent.ainvoke ---")
    for i, m in enumerate(result["messages"]):
        if isinstance(m, HumanMessage):
            print(f"  msg[{i}] HumanMessage: {m.content!r}")
    await checkpointer_factory.aclose()


asyncio.run(main())