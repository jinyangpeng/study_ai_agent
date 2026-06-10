"""详细追踪 bind_tools 行为。"""
import os
import traceback
from dotenv import load_dotenv
load_dotenv(".env")

from langchain_community.chat_models.zhipuai import ChatZhipuAI
from langchain_core.tools import tool


@tool
def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"sunny in {city}"


chat = ChatZhipuAI(
    model="glm-4-flash",
    api_key=os.environ["ZAI_API_KEY"],
    streaming=False,
)

print("=== Test: bind_tools(tools, tool_choice='any') ===")
try:
    bound = chat.bind_tools([get_weather], tool_choice="any")
    print(f"  Returned: {type(bound).__name__}")
    print(f"  kwargs: {bound.kwargs}")
except Exception as e:
    print(f"  FAILED: {type(e).__name__}: {e}")
    traceback.print_exc()

print("\n=== Test: 调用 wrapper 的 bind_tools 源码 ===")
import inspect
src = inspect.getsource(chat.bind_tools)
print(src)
