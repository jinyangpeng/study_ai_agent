# -*- coding: utf-8 -*-
"""Phase 3 测试：API + 健康检查（#7 SSE 心跳 / #14 探针 / #23 OpenAPI / #24 限流）。"""
from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """TestClient（不触发 lifespan，避免连 DB）。"""
    from src.core.server import app

    return TestClient(app)


# ---------------------------------------------------------------------------
# #14 /live + /ready + /health 端点
# ---------------------------------------------------------------------------
def test_live_endpoint(client):
    """/live 总是返回 200（进程存活即 OK）。"""
    resp = client.get("/live")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "alive"
    assert "agent" in body


def test_ready_endpoint_registered(client):
    """/ready 端点已注册。"""
    resp = client.get("/ready")
    # 不连 DB 时应该 503（not_ready），但端点必须存在
    assert resp.status_code in (200, 503)
    body = resp.json()
    assert "status" in body
    assert "checkpointer" in body
    assert "mcp" in body


def test_health_endpoint_returns_status_code(client):
    """/health 在 degraded 时返回 503，正常时返回 200。"""
    resp = client.get("/health")
    # 不连 DB 时 cp_ok=False → degraded → 503
    assert resp.status_code in (200, 503)
    body = resp.json()
    assert "status" in body
    assert body["status"] in ("ok", "degraded")
    # 必须包含所有诊断字段
    assert "checkpointer" in body
    assert "mcp" in body
    assert "rate_limit" in body
    assert "strategies" in body


# ---------------------------------------------------------------------------
# #23 OpenAPI 元数据
# ---------------------------------------------------------------------------
def test_openapi_metadata(client):
    """OpenAPI 文档含 contact / license / tags 元数据。"""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    spec = resp.json()
    assert spec["info"]["title"] == "LangChain Agent API"
    assert "contact" in spec["info"]
    assert "license" in spec["info"]
    assert "tags" in spec
    tag_names = [t["name"] for t in spec["tags"]]
    assert "AG-UI" in tag_names
    assert "Health" in tag_names
    assert "Skills" in tag_names
    assert "Threads" in tag_names


def test_endpoints_have_tags(client):
    """端点已按分组打 tag。"""
    resp = client.get("/openapi.json")
    spec = resp.json()
    paths = spec["paths"]
    # /live 应该有 Health tag
    assert "Health" in paths["/live"]["get"]["tags"]
    assert "Health" in paths["/ready"]["get"]["tags"]
    assert "Health" in paths["/health"]["get"]["tags"]
    # /skeletons 应该有 Skills tag
    assert "Skills" in paths["/skeletons"]["get"]["tags"]
    # / 应该有 AG-UI tag
    assert "AG-UI" in paths["/"]["post"]["tags"]


# ---------------------------------------------------------------------------
# #24 Rate Limiting
# ---------------------------------------------------------------------------
def test_rate_limit_disabled_by_default(client):
    """默认 RATE_LIMIT_ENABLED=false，/health 的 rate_limit.enabled=False。"""
    resp = client.get("/health")
    body = resp.json()
    assert body["rate_limit"]["enabled"] is False


def test_rate_limit_429_when_enabled():
    """开启限流后，超过配额返回 429 + Retry-After header。

    直接测试 ``_SlidingWindowCounter`` 逻辑，避免依赖完整 app reload
    （app 已在 module level 创建，中间件实例不会随 reload 重建）。
    """
    from src.core.middleware.rate_limit import _SlidingWindowCounter

    # 配额 2，窗口 60s
    counter = _SlidingWindowCounter(max_requests=2, window_seconds=60.0)

    # 前两次允许
    allowed1, remaining1, _ = counter.check("1.2.3.4")
    allowed2, remaining2, _ = counter.check("1.2.3.4")
    assert allowed1 is True
    assert allowed2 is True
    assert remaining1 == 1  # 第一次后剩 1
    assert remaining2 == 0  # 第二次后剩 0

    # 第三次被限流
    allowed3, remaining3, retry_after = counter.check("1.2.3.4")
    assert allowed3 is False
    assert remaining3 == 0
    assert retry_after > 0
    assert retry_after <= 60.0

    # 不同 IP 不受影响
    allowed_other, _, _ = counter.check("5.6.7.8")
    assert allowed_other is True


def test_rate_limit_middleware_dispatch():
    """RateLimitMiddleware 在超配额时返回 429 JSONResponse。"""
    from starlette.applications import Starlette
    from starlette.responses import PlainTextResponse

    from src.core.middleware.rate_limit import (
        RateLimitMiddleware,
        _SlidingWindowCounter,
    )

    # 构造一个最小 app，只挂 RateLimitMiddleware
    app = Starlette()
    app.add_middleware(RateLimitMiddleware)

    # 直接替换中间件的计数器和配置，模拟"已超配额"
    # 找到 RateLimitMiddleware 实例（Starlette 把中间件包成 _MiddlewareFactory）
    # 更简单：直接测试 dispatch 逻辑
    middleware = RateLimitMiddleware(app)
    middleware._enabled = True
    middleware._paths = ["/api/chat"]
    # 用一个已满的计数器
    full_counter = _SlidingWindowCounter(max_requests=1, window_seconds=60.0)
    full_counter.check("test-ip")  # 用掉唯一配额
    middleware._counter = full_counter

    # 构造一个请求，模拟从 test-ip 来
    from starlette.requests import Request

    async def call_next(request):
        return PlainTextResponse("should not reach")

    # 用 asyncio.run 测试 async dispatch
    import asyncio

    async def run():
        # 构造 scope dict（Starlette Request 的底层）
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/chat",
            "headers": [],
            "query_string": b"",
            "client": ("test-ip", 12345),
            "server": ("testserver", 80),
            "scheme": "http",
            "root_path": "",
            "app": app,
        }
        request = Request(scope)
        response = await middleware.dispatch(request, call_next)
        return response

    response = asyncio.run(run())
    assert response.status_code == 429
    # 应有 Retry-After header
    assert "retry-after" in {k.lower() for k in response.headers.keys()}
    # 响应体应符合统一错误格式
    import json
    body = json.loads(response.body.decode())
    assert body["error"]["code"] == "RATE_LIMITED"
    assert "request_id" in body["error"]


# ---------------------------------------------------------------------------
# #7 SSE 心跳
# ---------------------------------------------------------------------------
def test_sse_heartbeat_module():
    """SSE 心跳模块可导入，核心 API 可用。"""
    from src.core.sse_heartbeat import HEARTBEAT_LINE, is_heartbeat, with_heartbeat

    assert HEARTBEAT_LINE == b": keep-alive\n\n"
    assert is_heartbeat(object()) is False

    # 心跳关闭（interval=0）→ 直接透传事件
    async def src_events():
        yield "event1"
        yield "event2"

    async def run():
        results = []
        async for item in with_heartbeat(src_events(), interval=0):
            results.append(item)
        return results

    results = asyncio.run(run())
    assert results == ["event1", "event2"]


def test_sse_heartbeat_emits_keepalive():
    """心跳启用时，长时间无事件会发心跳哨兵。"""
    from src.core.sse_heartbeat import is_heartbeat, with_heartbeat

    async def slow_events():
        yield "event1"
        # 模拟 LLM 思考 0.3 秒
        await asyncio.sleep(0.3)
        yield "event2"

    async def run():
        results = []
        async for item in with_heartbeat(slow_events(), interval=0.1):
            results.append(item)
        return results

    results = asyncio.run(run())
    # 应该有 event1, 至少一个心跳, event2
    assert results[0] == "event1"
    assert results[-1] == "event2"
    # 中间应该有心跳哨兵
    heartbeats = [r for r in results if is_heartbeat(r)]
    assert len(heartbeats) >= 1, f"应至少有一个心跳，got {results}"


def test_sse_heartbeat_propagates_exception():
    """主事件流抛异常时，心跳协程应被取消，异常重新抛出。"""
    from src.core.sse_heartbeat import with_heartbeat

    async def failing_events():
        yield "event1"
        raise RuntimeError("boom")

    async def run():
        async for _ in with_heartbeat(failing_events(), interval=0.1):
            pass

    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(run())
