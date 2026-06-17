"""日志配置。

复用了 study_ai_agent 的同款配色 / 格式风格，避免在多服务环境下视觉割裂。
"""
from __future__ import annotations

import logging
import sys

_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def setup_logging(level: str = "INFO") -> None:
    """初始化根 logger。幂等。"""
    root = logging.getLogger()
    if getattr(root, "_crm_mcp_configured", False):
        root.setLevel(level)
        return

    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    root.handlers[:] = [handler]
    root.setLevel(level)

    # 降低 MCP / uvicorn 噪音
    logging.getLogger("mcp.server.lowlevel.server").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    root._crm_mcp_configured = True  # type: ignore[attr-defined]


__all__ = ["setup_logging"]
