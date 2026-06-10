"""验证切到 langchain_openai 后，tool_choice='any' 等非 auto 值能透传给智谱。"""
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage

from src.providers import ModelConfig
from src.providers.zhipuai import ZhipuAIProvider


@tool
def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"{city}：晴天 25°C"


async def test(label, tool_choice):
    print(f"\n=== {label} ===")
    provider = ZhipuAIProvider()
    chat = provider.build_chat(ModelConfig(model_name="glm-5.1", priority=1))
    try:
        if tool_choice is None:
            bound = chat.bind_tools([get_weather])
        else:
            bound = chat.bind_tools([get_weather], tool_choice=tool_choice)
        result = await bound.ainvoke([HumanMessage(content=f"北京天气怎么样？")])
        print(f"  -> content = {result.content[:80]!r}")
        print(f"  -> tool_calls = {result.tool_calls}")
    except Exception as e:
        print(f"  -> FAIL [{type(e).__name__}]: {str(e)[:200]}")


async def main():
    await test("Test 1: bind_tools 无 tool_choice  (默认)", None)
    await test("Test 2: bind_tools tool_choice='any'  (之前会炸)", "any")
    await test("Test 3: bind_tools tool_choice='auto'", "auto")
    await test("Test 4: bind_tools tool_choice='none'", "none")


asyncio.run(main())
