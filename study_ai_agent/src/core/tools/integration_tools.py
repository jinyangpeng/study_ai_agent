# -*- coding: utf-8 -*-
"""集成工具 - 从外部 MCP server 动态加载 LangChain 工具。

企业级防护
----------
1. **加载超时** — ``t.join(timeout=30)`` + ``asyncio.wait_for(..., timeout=20)``，
   MCP server 卡住不会阻塞 agent 启动
2. **make_safe 包装** — 每个 MCP 工具用 :func:`make_safe` 包一层，异常转结构化
   JSON，不会让 graph panic
3. **断路器** — 每个 MCP server 独立跟踪失败次数，连续失败 N 次后跳过该 server，
   冷却期过后自动半开重试
4. **自动重连** — 后台定时任务检测工具数为 0 时自动重连（指数退避）

配置
----
通过环境变量 ``MCP_SERVERS`` 声明要连的 MCP server::

    MCP_SERVERS=crm=http://localhost:8001/mcp,foo=http://localhost:9000/mcp
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
import time

logger = logging.getLogger(__name__)

#: MCP 加载超时（秒）—— 线程级
_LOAD_TIMEOUT = 30
#: MCP get_tools 超时（秒）—— asyncio 级
_FETCH_TIMEOUT = 20


# ---------------------------------------------------------------------------
# 断路器
# ---------------------------------------------------------------------------
class _CircuitBreaker:
    """简单的 MCP server 断路器。

    状态机：
    * CLOSED → 正常，请求通过
    * OPEN → 连续失败 N 次，跳过该 server
    * HALF_OPEN → 冷却期过后，允许一次试探

    线程安全（内部加锁）。
    """

    def __init__(self, failure_threshold: int = 3, cooldown_seconds: float = 60.0):
        self._lock = threading.Lock()
        self._failures: dict[str, int] = {}
        self._opened_at: dict[str, float] = {}
        self._threshold = failure_threshold
        self._cooldown = cooldown_seconds

    def is_open(self, server_name: str) -> bool:
        """该 server 的断路器是否处于 OPEN 状态（应跳过）。"""
        with self._lock:
            failures = self._failures.get(server_name, 0)
            if failures < self._threshold:
                return False
            # 冷却期过了 → 半开（允许试探）
            opened = self._opened_at.get(server_name, 0)
            if time.time() - opened > self._cooldown:
                return False
            return True

    def record_success(self, server_name: str) -> None:
        with self._lock:
            self._failures.pop(server_name, None)
            self._opened_at.pop(server_name, None)

    def record_failure(self, server_name: str) -> None:
        with self._lock:
            self._failures[server_name] = self._failures.get(server_name, 0) + 1
            if self._failures[server_name] >= self._threshold:
                self._opened_at[server_name] = time.time()
                logger.warning(
                    "MCP server %s 断路器打开（连续失败 %d 次）",
                    server_name, self._failures[server_name],
                )

    def status(self) -> dict[str, dict]:
        """返回所有 server 的断路器状态（供 /health 端点用）。"""
        with self._lock:
            result = {}
            all_names = set(list(self._failures.keys()) + list(self._opened_at.keys()))
            for name in all_names:
                result[name] = {
                    "failures": self._failures.get(name, 0),
                    "circuit_open": self.is_open(name),
                }
            return result


#: 全局断路器实例
_circuit_breaker = _CircuitBreaker()


# ---------------------------------------------------------------------------
# 配置解析
# ---------------------------------------------------------------------------
def _parse_servers(config: str) -> dict[str, dict[str, str]]:
    """解析 ``name=url,name=url`` 为 ``MultiServerMCPClient`` 要的配置 dict。

    >>> _parse_servers("crm=http://localhost:8001/mcp")
    {'crm': {'url': 'http://localhost:8001/mcp', 'transport': 'streamable_http'}}
    """
    servers: dict[str, dict[str, str]] = {}
    for item in config.split(","):
        item = item.strip()
        if not item or "=" not in item:
            continue
        name, url = item.split("=", 1)
        name = name.strip()
        url = url.strip()
        if name and url:
            servers[name] = {"url": url, "transport": "streamable_http"}
    return servers


# ---------------------------------------------------------------------------
# MCP 工具加载（带超时 + 断路器 + make_safe）
# ---------------------------------------------------------------------------
def _run_async_in_thread(coro_factory, timeout: float = _LOAD_TIMEOUT):
    """在独立线程的事件循环里运行 async callable，带超时保护。

    如果 ``timeout`` 秒内未完成，放弃等待，返回 ``[]``。
    """
    result: list = []

    def _target() -> None:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            result.append(loop.run_until_complete(coro_factory()))
        except Exception as e:
            logger.warning("MCP 工具加载失败: %s", e)
            result.append([])
        finally:
            loop.close()

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    t.join(timeout=timeout)
    if t.is_alive():
        logger.warning(
            "MCP 工具加载超时（%ds），跳过。MCP server 可能卡住。", timeout
        )
        return []
    return result[0] if result else []


def _load_mcp_tools() -> list:
    """同步加载所有 MCP server 的工具，返回 LangChain BaseTool 列表。

    每个工具会用 :func:`make_safe` 包一层异常防护。
    断路器处于 OPEN 状态的 server 会被跳过。
    """
    config = os.getenv("MCP_SERVERS", "")
    if not config:
        logger.info("MCP_SERVERS 未配置，INTEGRATION_TOOLS 为空")
        return []

    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError:
        logger.warning(
            "langchain-mcp-adapters 未安装，MCP 工具不可用。"
            "请 pip install langchain-mcp-adapters"
        )
        return []

    all_servers = _parse_servers(config)
    if not all_servers:
        logger.warning("MCP_SERVERS 配置解析为空: %r", config)
        return []

    # 过滤掉断路器打开的 server
    active_servers = {
        name: cfg for name, cfg in all_servers.items()
        if not _circuit_breaker.is_open(name)
    }
    skipped = set(all_servers.keys()) - set(active_servers.keys())
    if skipped:
        logger.info("MCP servers 被断路器跳过: %s", list(skipped))

    if not active_servers:
        logger.warning("所有 MCP server 断路器均打开，INTEGRATION_TOOLS 为空")
        return []

    logger.info("正在连接 MCP servers: %s", list(active_servers.keys()))

    async def _fetch():
        client = MultiServerMCPClient(active_servers)
        return await asyncio.wait_for(
            client.get_tools(), timeout=_FETCH_TIMEOUT
        )

    try:
        tools = _run_async_in_thread(_fetch)
    except Exception as e:
        logger.warning("MCP 工具加载异常: %s", e)
        # 记录断路器失败
        for name in active_servers:
            _circuit_breaker.record_failure(name)
        return []

    # 加载成功 → 记录断路器成功
    for name in active_servers:
        _circuit_breaker.record_success(name)

    # #6 make_safe 包装：每个 MCP 工具加异常防护
    tools = [_make_tool_safe(tool) for tool in tools]

    logger.info("从 MCP 加载了 %d 个工具", len(tools))
    return tools


def _make_tool_safe(tool):
    """给 MCP 工具包一层 :func:`make_safe` 异常防护。

    MCP 工具的 ``_arun`` 抛异常会直接冒泡到 LangGraph 的 ``_panic_or_proceed``，
    导致整个 graph panic、SSE 流被掐断。``make_safe`` 把异常转成结构化 JSON，
    LLM 看到后能优雅降级。
    """
    try:
        from src.core.tools.safe_tool import make_safe
        return make_safe(tool)
    except ImportError:
        logger.warning("safe_tool.make_safe 不可用，MCP 工具无异常防护")
        return tool


# ---------------------------------------------------------------------------
# 热重载
# ---------------------------------------------------------------------------
_reload_lock = threading.Lock()


def reload() -> list:
    """重新加载 MCP 工具（供热重载端点 ``POST /admin/skills/reload`` 调用）。

    重新读 ``MCP_SERVERS`` 环境变量 + 重新连所有 server。调用后
    ``INTEGRATION_TOOLS`` 会被原地替换（保持 list 引用不变，避免已 import
    它的模块拿到过期引用）。

    线程安全：用锁保护，防止并发 reload 导致 list 中间态。
    """
    with _reload_lock:
        new_tools = _load_mcp_tools()
        INTEGRATION_TOOLS.clear()
        INTEGRATION_TOOLS.extend(new_tools)
        logger.info("MCP 工具热重载完成: %d tools", len(INTEGRATION_TOOLS))
        return INTEGRATION_TOOLS


# ---------------------------------------------------------------------------
# 自动重连
# ---------------------------------------------------------------------------
_auto_reconnect_started = False


def start_auto_reconnect(interval: float = 60.0) -> None:
    """启动后台自动重连线程。

    每 ``interval`` 秒检测一次：如果 ``MCP_SERVERS`` 已配置但
    ``INTEGRATION_TOOLS`` 为空（说明之前加载失败），自动触发 reload。
    用指数退避避免频繁重连。
    """
    global _auto_reconnect_started
    if _auto_reconnect_started:
        return
    _auto_reconnect_started = True

    def _watcher():
        backoff = interval
        while True:
            time.sleep(backoff)
            config = os.getenv("MCP_SERVERS", "")
            if not config:
                continue
            if len(INTEGRATION_TOOLS) > 0:
                backoff = interval  # 恢复正常间隔
                continue
            # 工具数为 0 → 尝试重连
            logger.info("自动重连：MCP 工具数为 0，尝试 reload...")
            try:
                reload()
            except Exception as e:
                logger.warning("自动重连失败: %s", e)
            # 指数退避：失败后间隔翻倍，上限 5 分钟
            if len(INTEGRATION_TOOLS) == 0:
                backoff = min(backoff * 2, 300)
            else:
                backoff = interval

    t = threading.Thread(target=_watcher, daemon=True, name="mcp-auto-reconnect")
    t.start()
    logger.info("MCP 自动重连已启动（间隔 %ds）", int(interval))


# ---------------------------------------------------------------------------
# 健康检查
# ---------------------------------------------------------------------------
def mcp_health() -> dict[str, any]:
    """返回 MCP 集成的健康状态（供 /health 端点调用）。"""
    config = os.getenv("MCP_SERVERS", "")
    if not config:
        return {"configured": False, "tool_count": 0, "servers": {}}

    servers = _parse_servers(config)
    cb_status = _circuit_breaker.status()
    return {
        "configured": True,
        "tool_count": len(INTEGRATION_TOOLS),
        "servers": {
            name: {
                "url": cfg["url"],
                "circuit_open": _circuit_breaker.is_open(name),
                **cb_status.get(name, {"failures": 0}),
            }
            for name, cfg in servers.items()
        },
    }


# 模块加载时拉一次。MCP server 不可达 -> 空列表，不阻塞 agent。
INTEGRATION_TOOLS: list = _load_mcp_tools()

# 启动自动重连
start_auto_reconnect()


# ---------------------------------------------------------------------------
# HITL 规则自动生成
# ---------------------------------------------------------------------------
_WRITE_TOOL_KEYWORDS: tuple[str, ...] = (
    "create", "update", "delete", "remove", "convert",
    "complete", "advance", "send", "submit", "cancel",
    "archive", "restore", "assign", "transfer", "merge",
    "close", "approve", "reject", "activate", "deactivate",
)


def _is_write_tool(tool) -> bool:
    """判断一个 MCP 工具是否是写操作（需要 HITL 审批）。

    判断顺序：
    1. MCP annotations（如果 langchain-mcp-adapters 暴露了 ``readOnlyHint``
       / ``destructiveHint``，优先用它们）
    2. 工具名模式匹配（兜底）
    """
    metadata = getattr(tool, "metadata", None) or {}
    annotations = metadata.get("annotations") if isinstance(metadata, dict) else None
    if annotations:
        if annotations.get("readOnlyHint", False):
            return False
        if annotations.get("destructiveHint", False):
            return True

    name = (getattr(tool, "name", "") or "").lower()
    return any(kw in name for kw in _WRITE_TOOL_KEYWORDS)


def get_integration_hitl_rules() -> dict[str, dict[str, list[str]]]:
    """为所有已加载的 MCP 写操作工具自动生成 HITL 审批规则。"""
    return {
        tool.name: {"allowed_decisions": ["approve", "reject"]}
        for tool in INTEGRATION_TOOLS
        if _is_write_tool(tool)
    }


__all__ = [
    "INTEGRATION_TOOLS",
    "reload",
    "get_integration_hitl_rules",
    "mcp_health",
    "start_auto_reconnect",
]
