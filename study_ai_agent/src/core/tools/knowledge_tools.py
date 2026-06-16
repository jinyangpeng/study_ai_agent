"""知识库工具 - 知识库查询（Wikipedia 包装）。

代理控制
========

Wikipedia 工具本身不读 env var 也不会走代理（默认行为）。
当 :func:`src.core.tools.proxy.should_use_proxy` 判定 ``wikipedia`` 命中
白名单时，我们把 ``_run`` / ``arun`` 包了一层 :func:`use_temp_env_proxy`
上下文管理器，临时把 ``HTTP_PROXY`` / ``HTTPS_PROXY`` 注入到 env，调用
完立即还原。这样既能让 wikipedia 走代理，又不会污染 LLM 供应商等
其他模块的请求。
"""
# -*- coding: utf-8 -*-
import logging

from src.core.tools.proxy import use_temp_env_proxy

logger = logging.getLogger(__name__)

try:
    from langchain_community.tools import WikipediaQueryRun
    from langchain_community.utilities import WikipediaAPIWrapper

    from src.core.tools.safe_tool import make_safe

    class _ProxyAwareWikipediaQueryRun(WikipediaQueryRun):
        """WikipediaQueryRun 的代理感知 + 异常安全版。

        ``_run`` / ``_arun`` 在外层包 ``use_temp_env_proxy``，
        然后用 :func:`src.core.tools.safe_tool.make_safe` 给
        实例本身加 try/except 包装（不是改类）：

        * 任何 ``Exception``（网络超时、HTTP 错误、解析失败）都会被
          转成结构化 JSON 错误返回给 LLM，让 agent 优雅降级
        * ``BaseException``（CancelledError 等）原样上抛
        """

        def _run(self, *args, **kwargs):  # type: ignore[override]
            with use_temp_env_proxy("wikipedia"):
                return super()._run(*args, **kwargs)

        async def _arun(self, *args, **kwargs):  # type: ignore[override]
            with use_temp_env_proxy("wikipedia"):
                return await super()._arun(*args, **kwargs)

    wikipedia = make_safe(_ProxyAwareWikipediaQueryRun(api_wrapper=WikipediaAPIWrapper()))
    KNOWLEDGE_TOOLS = [wikipedia]
except ImportError as e:
    # ``wikipedia``（PyPI 包）是 :class:`WikipediaAPIWrapper` 委派给的
    # 三方包。如果没装，我们优雅降级，agent 其余部分照常工作。
    logger.warning("knowledge_tools unavailable (missing dependency: %s)", e)
    wikipedia = None  # type: ignore[assignment]
    KNOWLEDGE_TOOLS = []

__all__ = ["KNOWLEDGE_TOOLS", "wikipedia"]
