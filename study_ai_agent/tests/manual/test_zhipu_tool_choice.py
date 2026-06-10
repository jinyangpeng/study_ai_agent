"""验证 ChatZhipuAI 对 tool_choice 的限制。"""
import os
from dotenv import load_dotenv
load_dotenv(".env")

from langchain_community.chat_models.zhipuai import ChatZhipuAI
from langchain_core.tools import tool


@tool
def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"sunny in {city}"


def test(label, **kwargs):
    print(f"\n{label}")
    try:
        chat = ChatZhipuAI(
            model="glm-4-flash",
            api_key=os.environ["ZAI_API_KEY"],
            streaming=False,
        )
        bound = chat.bind_tools([get_weather], **kwargs)
        print(f"  -> OK   kwargs={kwargs}")
    except Exception as e:
        print(f"  -> FAIL [{type(e).__name__}]: {str(e)[:200]}")


test("Test 1: bind_tools(tools) without tool_choice  -- 不传")
test("Test 2: bind_tools(tools, tool_choice='any')   -- 触发 bug")
test("Test 3: bind_tools(tools, tool_choice='auto')  -- 应 OK")
test("Test 4: bind_tools(tools, tool_choice='none')  -- 触发 bug")
test("Test 5: bind_tools(tools, tool_choice={'type':'function','function':{'name':'get_weather'}}) -- 触发 bug")
