"""强制 tool_choice='auto' 看是否能端到端跑通 tool calling。"""
import asyncio
import os
from dotenv import load_dotenv
load_dotenv(".env")

from langchain_community.chat_models.zhipuai import ChatZhipuAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage


@tool
def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"晴天，{city}当前温度 25°C"


async def main():
    chat = ChatZhipuAI(
        model="glm-4-flash",
        api_key=os.environ["ZAI_API_KEY"],
        streaming=False,
    )

    # 1. 不用 bind_tools，手动用 .bind(tools=..., tool_choice='auto')
    print("=== Test A: 手动 bind tools+tool_choice='auto' ===")
    try:
        from langchain_core.utils.function_calling import convert_to_openai_tool
        formatted_tools = [convert_to_openai_tool(get_weather)]
        bound = chat.bind(tools=formatted_tools, tool_choice="auto")
        result = await bound.ainvoke([HumanMessage(content="北京天气怎么样？")])
        print(f"  -> result.content = {result.content!r}")
        print(f"  -> tool_calls = {result.tool_calls}")
    except Exception as e:
        print(f"  -> FAIL: {type(e).__name__}: {e}")

    # 2. 不用 tool_choice，让 API 自行决定
    print("\n=== Test B: 手动 bind tools，不传 tool_choice ===")
    try:
        from langchain_core.utils.function_calling import convert_to_openai_tool
        formatted_tools = [convert_to_openai_tool(get_weather)]
        bound = chat.bind(tools=formatted_tools)
        result = await bound.ainvoke([HumanMessage(content="北京天气怎么样？")])
        print(f"  -> result.content = {result.content!r}")
        print(f"  -> tool_calls = {result.tool_calls}")
    except Exception as e:
        print(f"  -> FAIL: {type(e).__name__}: {e}")

    # 3. 用 monkey-patched bind_tools 强制返回 "auto"
    print("\n=== Test C: monkey-patch bind_tools 强制 tool_choice='auto' ===")
    original_bind_tools = chat.bind_tools

    def patched_bind_tools(tools, *, tool_choice=None, **kwargs):
        # 静默把所有 tool_choice 改成 "auto"
        return original_bind_tools(tools, tool_choice="auto" if tool_choice else None, **kwargs)

    chat.bind_tools = patched_bind_tools
    try:
        bound = chat.bind_tools([get_weather], tool_choice="any")  # 显式传 any
        result = await bound.ainvoke([HumanMessage(content="北京天气怎么样？")])
        print(f"  -> result.content = {result.content!r}")
        print(f"  -> tool_calls = {result.tool_calls}")
    except Exception as e:
        print(f"  -> FAIL: {type(e).__name__}: {e}")


asyncio.run(main())
