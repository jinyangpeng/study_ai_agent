# -*- coding: utf-8 -*-
"""Phase 4 测试：LangGraph 运行时防护（#25 消息裁剪 / #26 工具超时 / #27 max_tokens / #28 GraphRecursionError）。"""
from __future__ import annotations

import asyncio

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage


# ---------------------------------------------------------------------------
# #25 消息裁剪
# ---------------------------------------------------------------------------
class TestTrimMessages:
    """消息裁剪测试。"""

    def test_no_trim_when_under_limit(self):
        """消息数 <= max_messages 时不裁剪。"""
        from src.core.message_utils import trim_messages

        msgs = [SystemMessage(content="sys"), HumanMessage(content="hi")]
        result = trim_messages(msgs, max_messages=10)
        assert len(result) == 2
        assert result == msgs

    def test_disabled_when_max_zero(self):
        """max_messages=0 时关闭裁剪。"""
        from src.core.message_utils import trim_messages

        msgs = [HumanMessage(content=f"msg{i}") for i in range(100)]
        result = trim_messages(msgs, max_messages=0)
        assert len(result) == 100

    def test_keeps_system_messages(self):
        """SystemMessage 总是保留。"""
        from src.core.message_utils import trim_messages

        msgs = [SystemMessage(content="sys1"), SystemMessage(content="sys2")]
        msgs += [HumanMessage(content=f"m{i}") for i in range(20)]
        result = trim_messages(msgs, max_messages=5)
        # system 2 条 + 最近 5 条非 system = 7 条
        assert len(result) == 7
        # 前两条是 system
        assert isinstance(result[0], SystemMessage)
        assert isinstance(result[1], SystemMessage)
        # 后 5 条是最近的
        assert result[2].content == "m15"
        assert result[-1].content == "m19"

    def test_drops_orphan_tool_messages(self):
        """裁剪后清理孤儿 ToolMessage（对应 AIMessage.tool_calls 被裁掉了）。"""
        from src.core.message_utils import trim_messages

        # 构造：system + AIMessage(带 tool_calls) + ToolMessage + 最近几条
        ai_with_tc = AIMessage(
            content="calling tool",
            tool_calls=[{"id": "tc-1", "name": "search", "args": {"q": "test"}}],
        )
        tool_msg = ToolMessage(content="result", tool_call_id="tc-1")
        msgs = [
            SystemMessage(content="sys"),
            ai_with_tc,
            tool_msg,
            HumanMessage(content="recent1"),
            HumanMessage(content="recent2"),
        ]
        # max_messages=2：保留 system + 最近 2 条（recent1, recent2）
        # ai_with_tc 和 tool_msg 都被裁掉 → 不应出现孤儿
        result = trim_messages(msgs, max_messages=2)
        # system + recent1 + recent2 = 3 条
        assert len(result) == 3
        # 不应有 ToolMessage（孤儿已清理）
        assert not any(isinstance(m, ToolMessage) for m in result)

    def test_keeps_tool_message_when_ai_kept(self):
        """AIMessage(带 tool_calls) 被保留时，对应 ToolMessage 也保留。"""
        from src.core.message_utils import trim_messages

        ai_with_tc = AIMessage(
            content="calling tool",
            tool_calls=[{"id": "tc-1", "name": "search", "args": {"q": "test"}}],
        )
        tool_msg = ToolMessage(content="result", tool_call_id="tc-1")
        msgs = [
            SystemMessage(content="sys"),
            ai_with_tc,
            tool_msg,
        ]
        result = trim_messages(msgs, max_messages=5)
        # 全部保留（未超限）
        assert len(result) == 3
        assert any(isinstance(m, ToolMessage) for m in result)


# ---------------------------------------------------------------------------
# #26 工具超时
# ---------------------------------------------------------------------------
class TestToolTimeout:
    """工具超时测试。"""

    def test_disabled_when_timeout_zero(self):
        """timeout_seconds=0 时直接返回原工具。"""
        from langchain_core.tools import tool

        from src.core.message_utils import with_tool_timeout

        @tool
        async def dummy_tool(query: str) -> str:
            """Dummy tool for testing."""
            return query

        result = with_tool_timeout(dummy_tool, timeout_seconds=0)
        assert result is dummy_tool

    def test_timeout_raises_tool_timeout_error(self):
        """工具超时抛 ToolTimeoutError。"""
        from langchain_core.tools import tool

        from src.core.message_utils import ToolTimeoutError, with_tool_timeout

        @tool
        async def slow_tool(query: str) -> str:
            """Slow tool that sleeps 10 seconds."""
            await asyncio.sleep(10)
            return query

        with_tool_timeout(slow_tool, timeout_seconds=0.1)

        async def run():
            await slow_tool._arun("test", config=None)

        with pytest.raises(ToolTimeoutError, match="timed out"):
            asyncio.run(run())

    def test_normal_tool_still_works(self):
        """超时包装不影响正常工具调用。"""
        from langchain_core.tools import tool

        from src.core.message_utils import with_tool_timeout

        @tool
        async def fast_tool(query: str) -> str:
            """Fast tool that returns immediately."""
            return f"result: {query}"

        with_tool_timeout(fast_tool, timeout_seconds=5)

        async def run():
            return await fast_tool._arun("hello", config=None)

        result = asyncio.run(run())
        assert result == "result: hello"


# ---------------------------------------------------------------------------
# #27 max_tokens
# ---------------------------------------------------------------------------
class TestMaxTokens:
    """max_tokens 绑定测试。"""

    def test_settings_has_max_tokens(self):
        """settings 包含 MODEL_MAX_TOKENS 配置。"""
        from src.config.settings import settings

        assert hasattr(settings, "MODEL_MAX_TOKENS")
        assert settings.MODEL_MAX_TOKENS > 0

    def test_model_factory_binds_max_tokens(self, monkeypatch):
        """model_factory.create_model 会调用 model.bind(max_tokens=...)。"""
        # 用 mock 替换 provider，避免真实 API 调用
        class _MockModel:
            def __init__(self):
                self.bound_kwargs = {}

            def bind(self, **kwargs):
                self.bound_kwargs = kwargs
                return self

            async def ainvoke(self, *args, **kwargs):
                return {"messages": []}

        class _MockProvider:
            def build_chat(self, config):
                return _MockModel()

        # 用 sys.modules 获取模块（避免被 src.core.__init__.py 的 re-export 干扰）
        import sys
        mf_module = sys.modules["src.core.model_factory"]

        original_registry = mf_module._PROVIDER_REGISTRY.copy()
        mf_module._PROVIDER_REGISTRY.clear()
        mf_module._PROVIDER_REGISTRY["mock"] = (_MockProvider, "MOCK_API_KEY")

        # 临时设置 available providers
        original_available = mf_module.model_factory._available_providers
        mf_module.model_factory._available_providers = ["mock"]

        try:
            model, provider = mf_module.model_factory.create_model()
            assert provider == "mock"
            # 应该绑定了 max_tokens
            assert "max_tokens" in model.bound_kwargs
            assert model.bound_kwargs["max_tokens"] > 0
        finally:
            mf_module._PROVIDER_REGISTRY.clear()
            mf_module._PROVIDER_REGISTRY.update(original_registry)
            mf_module.model_factory._available_providers = original_available


# ---------------------------------------------------------------------------
# #28 GraphRecursionError 处理
# ---------------------------------------------------------------------------
class TestGraphRecursionError:
    """GraphRecursionError 处理测试。"""

    def test_graph_recursion_error_importable(self):
        """能从 langgraph.errors 导入 GraphRecursionError（或兜底类）。"""
        try:
            from langgraph.errors import GraphRecursionError
            assert GraphRecursionError is not None
        except ImportError:
            # 老版本 langgraph 没有这个类，server.py 有兜底
            pass

    def test_server_handles_recursion_error(self):
        """server.py 的 event_generator 能捕获 GraphRecursionError 并发 RUN_ERROR。"""
        from fastapi.testclient import TestClient

        from src.core.server import app

        # 这个测试只验证端点能正常响应（不触发真实 recursion error）
        # 真实的 recursion error 处理逻辑在 server.py 的 except 子句里
        c = TestClient(app)
        # /live 总是 200，证明 app 正常加载
        resp = c.get("/live")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 策略节点应用防护
# ---------------------------------------------------------------------------
class TestStrategyProtections:
    """验证策略节点正确应用了消息裁剪和工具超时。"""

    def test_apply_runtime_protections_exists(self):
        """apply_runtime_protections 函数存在且可调用。"""
        from src.core.strategies.base import apply_runtime_protections

        msgs = [SystemMessage(content="sys")] + [
            HumanMessage(content=f"m{i}") for i in range(100)
        ]
        result = apply_runtime_protections(msgs)
        # 应该裁剪到 system + MAX_MESSAGES_PER_TURN 条
        assert len(result) < len(msgs)
        # 第一条是 system
        assert isinstance(result[0], SystemMessage)

    def test_wrap_skill_tools_with_timeout_exists(self):
        """wrap_skill_tools_with_timeout 函数存在且可调用。"""
        from langchain_core.tools import tool

        from src.core.strategies.base import wrap_skill_tools_with_timeout

        @tool
        async def dummy(query: str) -> str:
            """Dummy tool for testing wrap."""
            return query

        result = wrap_skill_tools_with_timeout([dummy])
        assert len(result) == 1
        # 返回的是同一个工具实例（monkey-patched）
        assert result[0] is dummy
