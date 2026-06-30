"""工具注册表 - 按类别聚合工具列表。

设计上和 LangChain 时代的版本一致（一个模块对应一个分类，做防御性加载），
但条目现在是普通的 typed 函数，由 Pydantic AI 根据签名和 docstring 自动包装。

每个 tool 模块都做防御性加载：如果它的三方依赖缺失（例如 ``wikipedia``、
``ddgs``），对应的 ``XXX_TOOLS`` list 就降级为 ``[]`` 并打 warning。
这样不会因为单个可选包没装就把整个 agent server 拖死。
"""

# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib
import logging
from typing import NamedTuple

logger = logging.getLogger(__name__)


class _ToolModule(NamedTuple):
    """tool 模块的标记：dotted 路径 + 持有 list 的属性名。"""

    dotted_name: str
    attr: str


# 注册表显式列出来（而不是自动发现），原因：
#   * 启动成本可预期
#   * 缺失的模块会有清晰的日志行
#   * 新增工具只要 append 一行
_TOOL_MODULES: tuple[_ToolModule, ...] = (
    _ToolModule("src.core.tools.info_tools", "INFO_TOOLS"),
    _ToolModule("src.core.tools.search_tools", "SEARCH_TOOLS"),
    _ToolModule("src.core.tools.knowledge_tools", "KNOWLEDGE_TOOLS"),
    _ToolModule("src.core.tools.computation_tools", "COMPUTATION_TOOLS"),
    _ToolModule("src.core.tools.file_tools", "FILE_TOOLS"),
    _ToolModule("src.core.tools.database_tools", "DATABASE_TOOLS"),
    _ToolModule("src.core.tools.communication_tools", "COMMUNICATION_TOOLS"),
    _ToolModule("src.core.tools.integration_tools", "INTEGRATION_TOOLS"),
    _ToolModule("src.core.tools.safety_tools", "SAFETY_TOOLS"),
    _ToolModule("src.core.tools.utility_tools", "UTILITY_TOOLS"),
)


def _load_tools(dotted_name: str, attr: str) -> list:
    """import 一个 tool 模块并返回它的 ``XXX_TOOLS`` list。

    任何失败（import 错误、缺属性、类型不对）都返回 ``[]``，
    这样单个坏模块不会阻塞整个 agent 启动。
    """
    try:
        module = importlib.import_module(dotted_name)
        tools = getattr(module, attr, [])
        if not isinstance(tools, list):
            logger.warning(
                "%s.%s is not a list (got %s); treating as empty",
                dotted_name,
                attr,
                type(tools).__name__,
            )
            return []
        if tools:
            logger.info("Loaded %d tool(s) from %s", len(tools), dotted_name)
        else:
            logger.info("No tools registered in %s", dotted_name)
        return tools
    except Exception as e:  # noqa: BLE001 - 这里确实需要兜住任何异常
        logger.warning("Failed to load %s.%s: %s", dotted_name, attr, e)
        return []


# 公开的 per-category list。每个都是新 list，调用方可以安全修改
# （比如测试时）而不会影响其它分类。
INFO_TOOLS = _load_tools("src.core.tools.info_tools", "INFO_TOOLS")
SEARCH_TOOLS = _load_tools("src.core.tools.search_tools", "SEARCH_TOOLS")
KNOWLEDGE_TOOLS = _load_tools("src.core.tools.knowledge_tools", "KNOWLEDGE_TOOLS")
COMPUTATION_TOOLS = _load_tools("src.core.tools.computation_tools", "COMPUTATION_TOOLS")
FILE_TOOLS = _load_tools("src.core.tools.file_tools", "FILE_TOOLS")
DATABASE_TOOLS = _load_tools("src.core.tools.database_tools", "DATABASE_TOOLS")
COMMUNICATION_TOOLS = _load_tools("src.core.tools.communication_tools", "COMMUNICATION_TOOLS")
INTEGRATION_TOOLS = _load_tools("src.core.tools.integration_tools", "INTEGRATION_TOOLS")
SAFETY_TOOLS = _load_tools("src.core.tools.safety_tools", "SAFETY_TOOLS")
UTILITY_TOOLS = _load_tools("src.core.tools.utility_tools", "UTILITY_TOOLS")

# MCP 写操作工具的 HITL 审批规则（自动生成，零代码扩展）。
# 从 integration_tools 模块导入函数本身（不是调用结果），让调用方在
# 需要时动态获取最新规则（热重载后规则也会更新）。
from src.core.tools.integration_tools import get_integration_hitl_rules  # noqa: E402

# 展开后的 list，在 Pydantic AI Agent 构建时使用。缺失的分类贡献 ``[]``。
ALL_TOOLS: list = (
    INFO_TOOLS
    + SEARCH_TOOLS
    + KNOWLEDGE_TOOLS
    + COMPUTATION_TOOLS
    + FILE_TOOLS
    + DATABASE_TOOLS
    + COMMUNICATION_TOOLS
    + INTEGRATION_TOOLS
    + SAFETY_TOOLS
    + UTILITY_TOOLS
)

__all__ = [
    "ALL_TOOLS",
    "INFO_TOOLS",
    "SEARCH_TOOLS",
    "KNOWLEDGE_TOOLS",
    "COMPUTATION_TOOLS",
    "FILE_TOOLS",
    "DATABASE_TOOLS",
    "COMMUNICATION_TOOLS",
    "INTEGRATION_TOOLS",
    "SAFETY_TOOLS",
    "UTILITY_TOOLS",
    "get_integration_hitl_rules",
]
