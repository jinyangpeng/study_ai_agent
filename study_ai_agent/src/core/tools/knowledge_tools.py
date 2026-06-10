"""知识库工具 - 知识库查询（Wikipedia 包装）。"""
import logging

logger = logging.getLogger(__name__)

try:
    from langchain_community.tools import WikipediaQueryRun
    from langchain_community.utilities import WikipediaAPIWrapper

    wikipedia = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())
    KNOWLEDGE_TOOLS = [wikipedia]
except ImportError as e:
    # ``wikipedia``（PyPI 包）是 :class:`WikipediaAPIWrapper` 委派给的
    # 三方包。如果没装，我们优雅降级，agent 其余部分照常工作。
    logger.warning("knowledge_tools unavailable (missing dependency: %s)", e)
    wikipedia = None  # type: ignore[assignment]
    KNOWLEDGE_TOOLS = []

__all__ = ["KNOWLEDGE_TOOLS", "wikipedia"]
