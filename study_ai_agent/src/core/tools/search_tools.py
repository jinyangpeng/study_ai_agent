"""搜索工具 - Web 搜索（DuckDuckGo 包装）。

代理控制
========

与 :mod:`src.core.tools.knowledge_tools` 类似 —— 继承一份 :class:`DuckDuckGoSearchResults`
并把 ``_run`` / ``arun`` 包一层 :func:`src.core.tools.proxy.use_temp_env_proxy` 上下文。
这样 ``duckduckgo-search`` 库创建的 ``DDGS`` 实例会在 with 块内读到代理 env，
with 块外立即还原，LLM 供应商调用不受影响。
"""
# -*- coding: utf-8 -*-
import logging

from src.core.tools.proxy import use_temp_env_proxy

logger = logging.getLogger(__name__)

try:
    from langchain_community.tools import DuckDuckGoSearchResults

    class _ProxyAwareDuckDuckGoSearchResults(DuckDuckGoSearchResults):
        """DuckDuckGoSearchResults 的代理感知版。

        :class:`DuckDuckGoSearchResults` 的 ``.name`` 实际是
        ``"duckduckgo_results_json"``（与类名不一致），白名单里要写这个值。
        """

        def _run(self, *args, **kwargs):  # type: ignore[override]
            with use_temp_env_proxy("duckduckgo_results_json"):
                return super()._run(*args, **kwargs)

        async def _arun(self, *args, **kwargs):  # type: ignore[override]
            with use_temp_env_proxy("duckduckgo_results_json"):
                return await super()._arun(*args, **kwargs)

    search = _ProxyAwareDuckDuckGoSearchResults()
    SEARCH_TOOLS = [search]
except ImportError as e:
    # ``duckduckgo-search`` 是 :class:`DuckDuckGoSearchResults` 委派给的
    # 三方包。缺它 => 没有 web 搜索工具，agent 仍能启动。
    logger.warning("search_tools unavailable (missing dependency: %s)", e)
    search = None  # type: ignore[assignment]
    SEARCH_TOOLS = []

__all__ = ["SEARCH_TOOLS", "search"]
