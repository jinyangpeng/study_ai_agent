"""Tools 子包 - 全部 5 个实体的 MCP 工具实现。

各文件按实体拆分；统一在 :mod:`crm_mcp.server` 里 ``register(mcp)`` 全部注册。
"""

from __future__ import annotations

from crm_mcp.tools import (
    activities,
    contacts,
    customers,
    leads,
    opportunities,
)

__all__ = [
    "activities",
    "contacts",
    "customers",
    "leads",
    "opportunities",
]
