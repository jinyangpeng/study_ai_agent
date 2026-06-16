"""扒 DuckDuckGoSearchResults._run 的真实返回值，看 make_safe 包装后是否还保 tuple。"""
import inspect
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from langchain_community.tools import DuckDuckGoSearchResults

print("=== 1. 类的字段（pydantic）===")
print(f"  model_fields = {list(DuckDuckGoSearchResults.model_fields.keys())}")
ff = DuckDuckGoSearchResults.model_fields.get("response_format")
if ff:
    print(f"  response_format field = {ff}")
print()

print("=== 2. _run 源码 ===")
src = inspect.getsource(DuckDuckGoSearchResults._run)
print(src)
print()

print("=== 3. 实例化 + 直接调用 _run ===")
tool = DuckDuckGoSearchResults()
print(f"  实例 name           = {tool.name!r}")
print(f"  实例 response_format = {tool.response_format!r}")
print()

# 4. 让 make_safe 包前后对比
from src.core.tools.safe_tool import make_safe
raw = DuckDuckGoSearchResults()
safe = make_safe(raw)

print("=== 4. 包前 _run 返回类型 ===")
try:
    raw_result = raw._run("Python tutorial", max_results=1)
    print(f"  type = {type(raw_result).__name__}")
    if isinstance(raw_result, tuple):
        print(f"  tuple length = {len(raw_result)}")
        for i, x in enumerate(raw_result):
            print(f"  [{i}] type={type(x).__name__} str(x)={str(x)[:100]!r}")
    else:
        print(f"  value = {str(raw_result)[:200]!r}")
except Exception as e:
    print(f"  [EXC] {type(e).__name__}: {e}")

print()
print("=== 5. 包后 _run 返回类型 ===")
try:
    safe_result = safe._run("Python tutorial", max_results=1)
    print(f"  type = {type(safe_result).__name__}")
    if isinstance(safe_result, tuple):
        print(f"  tuple length = {len(safe_result)}")
        for i, x in enumerate(safe_result):
            print(f"  [{i}] type={type(x).__name__} str(x)={str(x)[:100]!r}")
    else:
        print(f"  value = {str(safe_result)[:200]!r}")
except Exception as e:
    print(f"  [EXC] {type(e).__name__}: {e}")
