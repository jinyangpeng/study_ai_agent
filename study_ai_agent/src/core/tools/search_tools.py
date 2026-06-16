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

    from src.core.tools.safe_tool import make_safe

    class _ProxyAwareDuckDuckGoSearchResults(DuckDuckGoSearchResults):
        """DuckDuckGoSearchResults 的代理感知 + 异常安全版。

        ``_run`` / ``_arun`` 在外层包 ``use_temp_env_proxy``，
        然后用 :func:`src.core.tools.safe_tool.make_safe` 给
        实例本身加 try/except 包装（不是改类）：

        * 任何 ``Exception``（网络超时、HTTP 错误、解析失败）都会被
          转成结构化 JSON 错误返回给 LLM，让 agent 优雅降级
        * 而不是 panic 上传把 langgraph 的 graph 搞崩
        * ``BaseException``（CancelledError 等）原样上抛

        :class:`DuckDuckGoSearchResults` 的 ``.name`` 实际是
        ``"duckduckgo_results_json"``（与类名不一致），白名单里要写这个值。
        """

        def _run(self, *args, **kwargs):  # type: ignore[override]
            with use_temp_env_proxy("duckduckgo_results_json"):
                return super()._run(*args, **kwargs)

        async def _arun(self, *args, **kwargs):  # type: ignore[override]
            with use_temp_env_proxy("duckduckgo_results_json"):
                return await super()._arun(*args, **kwargs)

    search = make_safe(_ProxyAwareDuckDuckGoSearchResults())
    SEARCH_TOOLS = [search]
except ImportError as e:
    # ``duckduckgo-search`` 是 :class:`DuckDuckGoSearchResults` 委派给的
    # 三方包。缺它 => 没有 web 搜索工具，agent 仍能启动。
    logger.warning("search_tools unavailable (missing dependency: %s)", e)
    search = None  # type: ignore[assignment]
    SEARCH_TOOLS = []

__all__ = ["SEARCH_TOOLS", "search"]
