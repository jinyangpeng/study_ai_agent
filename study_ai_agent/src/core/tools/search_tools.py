"""搜索工具 - Web 搜索（DuckDuckGo 包装）。"""
import logging

logger = logging.getLogger(__name__)

try:
    from langchain_community.tools import DuckDuckGoSearchResults

    search = DuckDuckGoSearchResults()
    SEARCH_TOOLS = [search]
except ImportError as e:
    # ``duckduckgo-search`` 是 :class:`DuckDuckGoSearchResults` 委派给的
    # 三方包。缺它 => 没有 web 搜索工具，agent 仍能启动。
    logger.warning("search_tools unavailable (missing dependency: %s)", e)
    search = None  # type: ignore[assignment]
    SEARCH_TOOLS = []

__all__ = ["SEARCH_TOOLS", "search"]
