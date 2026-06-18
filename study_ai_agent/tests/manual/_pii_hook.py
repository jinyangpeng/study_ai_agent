"""Debug: hook vs detector vs ainvoke."""
import sys, asyncio
sys.path.insert(0, ".")
from langchain.agents.middleware import PIIMiddleware
from langchain_core.messages import HumanMessage

m = PIIMiddleware("email", strategy="redact", apply_to_input=True)

text = "帮我发一份email给test@test.com，帮我向他问好并祝他生日快乐。"
print("text:", text)
print()
print("1) detector direct call:")
print("   matches:", m.detector(text))
print()
print("2) before_model hook (sync):")
state = {"messages": [HumanMessage(content=text)]}
result = m.before_model(state, None)
print("   returned:", result)
if result:
    print("   new content:", result["messages"][0].content)
print()
print("3) abefore_model hook (async):")
async def go():
    state = {"messages": [HumanMessage(content=text)]}
    result = await m.abefore_model(state, None)
    return result
r = asyncio.run(go())
print("   returned:", r)
if r:
    print("   new content:", r["messages"][0].content)