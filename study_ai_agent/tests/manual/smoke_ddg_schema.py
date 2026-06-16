"""扒 args_schema 和字段，看 LLM 看到的工具签名。"""
import inspect
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from langchain_community.tools import DuckDuckGoSearchResults

tool = DuckDuckGoSearchResults()

print("=== 1. args_schema ===")
print(f"  type = {type(tool.args_schema).__name__}")
print(f"  schema = {tool.args_schema.model_json_schema()}")
print()

print("=== 2. max_results 字段 ===")
print(f"  type(max_results) = {type(tool.max_results).__name__}")
print(f"  value = {tool.max_results!r}")
print()

print("=== 3. output_format 字段 ===")
print(f"  type = {type(tool.output_format).__name__}")
print(f"  value = {tool.output_format!r}")
print()

print("=== 4. 实际调 _run 用正确签名（不传 max_results）===")
try:
    result = tool._run("Python tutorial")
    print(f"  type = {type(result).__name__}")
    print(f"  is tuple = {isinstance(result, tuple)}")
    if isinstance(result, tuple):
        print(f"  len = {len(result)}")
        print(f"  [0] type = {type(result[0]).__name__} preview = {str(result[0])[:100]!r}")
        print(f"  [1] type = {type(result[1]).__name__} preview = {str(result[1])[:100]!r}")
    else:
        print(f"  value = {str(result)[:200]!r}")
except Exception as e:
    print(f"  [EXC] {type(e).__name__}: {e}")
print()

print("=== 5. _run 完整签名（看 default 都有谁）===")
sig = inspect.signature(tool._run)
for p_name, p in sig.parameters.items():
    print(f"  {p_name}: default={p.default!r}, kind={p.kind!r}")
