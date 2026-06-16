"""验证 safe_tool.py 能接住底层异常并返回结构化 JSON。"""
import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 1) 静态检查
from src.core.tools.safe_tool import SafeTool, make_safe, _format_error  # noqa: E402
print("[OK] safe_tool imports")

# 2) 格式函数
out = _format_error("foo", TimeoutError("connection refused"), ("hello world",), {"k": 1})
parsed = json.loads(out)
assert parsed["ok"] is False
assert parsed["tool"] == "foo"
assert "TimeoutError" in parsed["error"]
assert "connection refused" in parsed["error"]
assert parsed["args"]["_args_0"] == "hello world"
assert parsed["args"]["k"] == "1"
assert "hint" in parsed
print(f"[OK] _format_error 返回结构化 JSON: {list(parsed.keys())}")

# 3) make_safe 包装
from langchain_core.tools import BaseTool  # noqa: E402

class _Flaky(BaseTool):
    name: str = "flaky"
    description: str = "always fails"

    def _run(self, *args, **kwargs):
        raise RuntimeError("simulated network error")

    async def _arun(self, *args, **kwargs):
        raise ConnectionError("simulated conn reset")

flaky = make_safe(_Flaky())
sync_result = flaky._run("query", n=5)
parsed_sync = json.loads(sync_result)
assert parsed_sync["ok"] is False
assert parsed_sync["tool"] == "flaky"
assert "RuntimeError" in parsed_sync["error"]
assert isinstance(sync_result, str), "default response_format 应该返回 str"
print(f"[OK] make_safe._run 捕住异常，返回 str JSON: error={parsed_sync['error']}")

async_result = asyncio.run(flaky._arun("q", n=5))
parsed_async = json.loads(async_result)
assert parsed_async["ok"] is False
assert "ConnectionError" in parsed_async["error"]
assert isinstance(async_result, str)
print(f"[OK] make_safe._arun 捕住异常，返回 str JSON: error={parsed_async['error']}")

# 3b) content_and_artifact 工具应返回 2-tuple
class _FlakyArtifact(BaseTool):
    name: str = "flaky_artifact"
    description: str = "always fails, content_and_artifact"
    response_format: str = "content_and_artifact"

    def _run(self, *args, **kwargs):
        raise TimeoutError("connect timeout")

    async def _arun(self, *args, **kwargs):
        raise TimeoutError("arun timeout")

flaky_art = make_safe(_FlakyArtifact())
sync_result = flaky_art._run("q")
assert isinstance(sync_result, tuple), f"content_and_artifact 应该返回 tuple，实际 {type(sync_result).__name__}"
assert len(sync_result) == 2
content_str, artifact_dict = sync_result
assert isinstance(content_str, str)
assert isinstance(artifact_dict, dict)
parsed = json.loads(content_str)
assert parsed["ok"] is False
assert artifact_dict["ok"] is False
assert artifact_dict["error"] == parsed["error"]
print(f"[OK] content_and_artifact 工具返回 2-tuple, content={parsed['error'][:50]}")
print(f"     artifact 是 dict: keys={list(artifact_dict.keys())}")

async_result = asyncio.run(flaky_art._arun("q"))
assert isinstance(async_result, tuple) and len(async_result) == 2
print(f"[OK] content_and_artifact 工具 _arun 也返回 2-tuple")

# 4) CancelledError 不被吞掉（必须冒泡）
try:
    flaky._run()  # type: ignore[call-arg]
except Exception as e:
    print(f"  [info] 同步异常路径 OK: {type(e).__name__}")

# 模拟 CancelledError 路径
class _AlwaysCancelled(BaseTool):
    name: str = "cancelled"
    description: str = "raises CancelledError"

    def _run(self, *args, **kwargs):
        import asyncio as _a
        raise _a.CancelledError()

    async def _arun(self, *args, **kwargs):
        import asyncio as _a
        raise _a.CancelledError()

try:
    make_safe(_AlwaysCancelled())._run()
except asyncio.CancelledError:
    print("[OK] CancelledError 正确上抛（不被吞）")
except Exception as e:
    print(f"[FAIL] CancelledError 被吞了: {type(e).__name__}: {e}")
    sys.exit(1)

# 5) 验证真实 search_tools 加载没炸
from src.core.tools.search_tools import search  # noqa: E402
if search is not None:
    print(f"[OK] real search tool loaded: name={search.name!r}, type={type(search).__name__}")
    # 模拟超时：用一个无效 query + 关闭网络，触发 ddg 异常
    print()
    print("=== 真实场景：触发 DDG 真实异常，看 make_safe 接不接得住 ===")
    import os
    env_saved = {k: os.environ.pop(k, None) for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy")}
    try:
        # 把 ddgs 库路径里那个用不了的 backend 切走
        os.environ["DDGS_DEFAULT_BACKEND"] = "nonexistent_backend_xyz"
        try:
            result = search._run("对比dify和coze", max_results=1)
            # 看返回是字符串（错误 JSON）还是 dict（成功）
            if isinstance(result, str):
                try:
                    parsed = json.loads(result)
                    if parsed.get("ok") is False:
                        print(f"[OK] 真实异常被接住: {parsed['error'][:100]}")
                    else:
                        print(f"[?] 返回了非 ok:false 的 JSON: {parsed}")
                except json.JSONDecodeError:
                    print(f"[?] 返回了非 JSON 字符串: {result[:200]}")
            else:
                print(f"[SKIP] DDG 居然成功了: {str(result)[:80]}")
        except Exception as e:
            print(f"[FAIL] _run 还是抛了: {type(e).__name__}: {e}")
            sys.exit(1)
    finally:
        os.environ.pop("DDGS_DEFAULT_BACKEND", None)
        for k, v in env_saved.items():
            if v is not None:
                os.environ[k] = v

print()
print("=" * 60)
print("[ALL OK] safe_tool 防护就绪")

# 6) SafeTool 混入 content_and_artifact 工具：异常路径也必须返 2-tuple
#    之前 SafeTool 写死了 _format_error(str)，对 content_and_artifact 工具会再炸 2-tuple 错。
#    SafeTool 的设计：自身 _run 用 super() 触发实际工具逻辑。
#    要让 SafeTool._run 的 super() 调到抛错的方法，需要一个 BaseTool 子类做"真工具"，
#    且 MRO 顺序是 _FlakyArtifactSubclass -> SafeTool -> _BaseFlakyTool -> BaseTool。
class _BaseFlakyTool(BaseTool):
    name: str = "base_flaky"
    description: str = "underlying tool, always fails"

    def _run(self, *args, **kwargs):
        raise TimeoutError("base _run timeout")

    async def _arun(self, *args, **kwargs):
        raise TimeoutError("base _arun timeout")

class _FlakyArtifactSubclass(SafeTool, _BaseFlakyTool):
    name: str = "flaky_artifact_subclass"
    description: str = "mixin: SafeTool + content_and_artifact, always fails"
    response_format: str = "content_and_artifact"
    # 不重写 _run/_arun，让 SafeTool._run 的 super() 走到 _BaseFlakyTool._run 抛错

mixin = _FlakyArtifactSubclass()
sync_result = mixin._run("q")
assert isinstance(sync_result, tuple) and len(sync_result) == 2, \
    f"SafeTool 混入 content_and_artifact 应返 2-tuple，实际 {type(sync_result).__name__}"
parsed = json.loads(sync_result[0])
assert parsed["ok"] is False and parsed["tool"] == "flaky_artifact_subclass"
async_result = asyncio.run(mixin._arun("q"))
assert isinstance(async_result, tuple) and len(async_result) == 2
print("[OK] SafeTool 混入 content_and_artifact 工具异常路径也返 2-tuple")
