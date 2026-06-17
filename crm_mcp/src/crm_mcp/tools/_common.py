"""工具层共享工具。

- ``_read_only_annotations`` / ``_write_annotations`` 统一产出 MCP tool annotations
- ``_common_list_kwargs`` 抽出 ListQuery -> store 层调用的关键字段
- ``safe_tool_call`` 装饰器：把任何异常走 :func:`crm_mcp.formatters.format_error` 渲染成可读字符串
- ``register(mcp)`` 由各 entity tool 模块实现
"""
from __future__ import annotations

import functools
import logging
from datetime import datetime, timezone
from typing import Any, Callable

from crm_mcp.config import settings
from crm_mcp.formatters import format_error
from crm_mcp.models import ListQuery

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 注解 helper
# ---------------------------------------------------------------------------
def read_only_annotations(title: str) -> dict[str, Any]:
    return {
        "title": title,
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }


def write_annotations(title: str, *, destructive: bool = False) -> dict[str, Any]:
    return {
        "title": title,
        "readOnlyHint": False,
        "destructiveHint": destructive,
        "idempotentHint": not destructive,
        "openWorldHint": False,
    }


# ---------------------------------------------------------------------------
# 时间 / 分页 / 错误
# ---------------------------------------------------------------------------
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def resolve_page_size(q: ListQuery) -> tuple[int, int]:
    limit = q.limit or settings.DEFAULT_PAGE_SIZE
    limit = min(limit, settings.MAX_PAGE_SIZE)
    return q.offset, limit


def safe_tool_call(fn: Callable[..., str]) -> Callable[..., str]:
    """装饰器：工具内异常统一格式化。

    放在工具函数最外层（注册到 ``@mcp.tool`` 之前），确保不破坏
    FastMCP 期望的 async 签名。
    """
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except Exception as e:  # noqa: BLE001 - 工具边界需要兜所有
            logger.exception("CRM tool '%s' failed", getattr(fn, "__name__", "?"))
            return format_error(e)

    return wrapper


__all__ = [
    "read_only_annotations",
    "write_annotations",
    "now_utc",
    "resolve_page_size",
    "safe_tool_call",
]
