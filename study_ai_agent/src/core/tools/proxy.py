"""网络类工具的代理控制辅助。

为什么需要这个模块
==================

Python 默认不读系统代理（不像浏览器）。``requests`` / ``httpx`` /
``duckduckgo-search`` / ``wikipedia`` 都会读取 ``HTTP_PROXY`` /
``HTTPS_PROXY`` / ``NO_PROXY`` 这几个环境变量来决定是否走代理。

如果直接在 ``.env`` 里设了 ``HTTP_PROXY=...``，那所有出网请求都会走代理，
包括一些本不需要代理的（比如智谱 GLM 在国内域名下其实直连就行）。
这对"按需开代理"的开发模式不友好。

设计目标
========

- **默认全部走直连**：环境里没配 ``TOOL_HTTP_PROXY`` / 白名单为空时所有工具都直连。
- **白名单机制**：只有 ``TOOL_PROXY_WHITELIST`` 显式列出的 tool 才走代理。
  白名单为空时等于"所有 tool 都不走代理"。
- **临时切 env，不污染全局**：通过 :func:`use_temp_env_proxy` 上下文管理器，
  在工具执行前临时把代理写进 ``HTTP_PROXY`` / ``HTTPS_PROXY``，执行后立刻还原。
  这样 LLM 供应商调用、其他直连工具都不受影响。

环境变量约定
============

- ``TOOL_HTTP_PROXY`` —— 代理地址（例 ``http://127.0.0.1:10809``）。
- ``TOOL_PROXY_WHITELIST`` —— 逗号分隔的 tool 名称列表，例
  ``wikipedia,duckduckgo_search``。大小写不敏感、首尾空白忽略。
  tool 名 = ``BaseTool.name``（通常 langchain 工具的 ``name`` 字段）。
"""

# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Iterator, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 内部：env 读取（不缓存，env 可能动态改）
# ---------------------------------------------------------------------------


def _read_proxy_url() -> str:
    """读取代理 URL，优先 ``TOOL_HTTP_PROXY``，回退到 ``HTTP_PROXY``。"""
    return os.getenv("TOOL_HTTP_PROXY", "") or os.getenv("HTTP_PROXY", "")


def _read_whitelist() -> frozenset[str]:
    """读取 ``TOOL_PROXY_WHITELIST``，解析为小写 tool 名集合。"""
    raw = os.getenv("TOOL_PROXY_WHITELIST", "") or ""
    items = [x.strip().lower() for x in raw.split(",") if x.strip()]
    return frozenset(items)


# ---------------------------------------------------------------------------
# 公共 API
# ---------------------------------------------------------------------------
def get_proxy_url() -> Optional[str]:
    """返回当前生效的代理 URL（去掉尾部 ``/``）；未配置时返回 ``None``。"""
    url = _read_proxy_url().strip().rstrip("/")
    return url or None


def should_use_proxy(tool_name: str) -> bool:
    """判断指定 tool 是否应当走代理。

    判定规则：
      1) ``TOOL_HTTP_PROXY`` 未配置 → 全部走直连，返回 False
      2) 白名单为空 → 全部走直连，返回 False
      3) ``tool_name`` 在白名单中 → True
      4) 其他 → False

    Args:
        tool_name: 工具名（与 langchain ``BaseTool.name`` 一致），大小写不敏感。
    """
    if not tool_name:
        return False
    if not get_proxy_url():
        return False
    wl = _read_whitelist()
    if not wl:
        return False
    return tool_name.strip().lower() in wl


@contextmanager
def use_temp_env_proxy(tool_name: str) -> Iterator[None]:
    """上下文管理器：在 with 块内临时把代理写进 ``HTTP_PROXY`` /
    ``HTTPS_PROXY`` 环境变量，退出时还原。

    适用场景：langchain 的 ``DuckDuckGoSearchAPIWrapper`` /
    ``WikipediaAPIWrapper`` 没暴露 proxy 参数，内部用 ``requests`` /
    ``duckduckgo_search.DDGS()`` 创建客户端，会读 env var。
    通过临时切 env var 让它们走代理，且不会污染 with 块外的请求
    （包括 LLM 供应商调用）。

    用法::

        from langchain_core.tools import BaseTool
        from src.core.tools.proxy import use_temp_env_proxy

        class ProxyAwareWikipedia(WikipediaQueryRun):
            def _run(self, *args, **kwargs):
                with use_temp_env_proxy("wikipedia"):
                    return super()._run(*args, **kwargs)

    如果工具不在白名单中 / 未配代理，with 块什么也不做（无开销）。
    """
    if not should_use_proxy(tool_name):
        yield
        return

    proxy = get_proxy_url()
    if not proxy:
        yield
        return

    saved: dict[str, Optional[str]] = {
        k: os.environ.get(k) for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy")
    }
    os.environ["HTTP_PROXY"] = proxy
    os.environ["HTTPS_PROXY"] = proxy
    os.environ["http_proxy"] = proxy
    os.environ["https_proxy"] = proxy
    try:
        logger.debug("[proxy] %s 走代理: %s", tool_name, proxy)
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


__all__ = [
    "get_proxy_url",
    "should_use_proxy",
    "use_temp_env_proxy",
]
