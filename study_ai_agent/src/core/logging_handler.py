# -*- coding: utf-8 -*-
"""LLM 调用和 tool 调用的日志回调 handler。

改用标准 :mod:`logging` 模块，废弃 ``print()`` + 手写文件 IO 的旧实现。
日志统一走 ``app`` logger（由 :mod:`src.logging.setup` 配置），自动获得：
* 结构化 JSON / 文本格式
* 日志轮转（TimedRotatingFileHandler）
* request_id 注入
"""

import logging

from langchain_core.callbacks import BaseCallbackHandler

logger = logging.getLogger("app.callback")


class LoggingHandler(BaseCallbackHandler):
    """把 LLM 和 tool 调用日志打到标准 ``app.callback`` logger。"""

    name = "logger"

    def on_chat_model_start(self, serialized, messages, **kwargs):
        try:
            prompts = [str(m)[:500] for m in (messages[0] if messages else [])]
        except Exception:
            prompts = [str(messages)[:500]]
        logger.info("[model-start] prompts=%s", prompts)

    def on_chat_model_end(self, response, **kwargs):
        try:
            output = str(response)[:500]
        except Exception:
            output = "..."
        logger.info("[model-end] output=%s", output)

    def on_tool_start(self, serialized, input_str, **kwargs):
        name = serialized.get("name", "unknown") if isinstance(serialized, dict) else "unknown"
        logger.info("[tool-start] tool=%s input=%s", name, input_str)

    def on_tool_end(self, output, **kwargs):
        logger.info("[tool-end] output=%s", output)

    def on_tool_error(self, error, **kwargs):
        logger.error("[tool-error] %s: %s", type(error).__name__, error)
