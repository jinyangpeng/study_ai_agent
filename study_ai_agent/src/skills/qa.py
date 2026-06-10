"""QA Skill - 常规智能问答 Agent。

工具集
------
* Web 搜索、知识库、信息查询
* **纯只读** - 不挂任何 FILE_TOOLS、SHELL_TOOLS、git 工具。

HITL 策略
---------
空 dict —— read-only agent 没有副作用，所以不需要任何审批门禁。
"""
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.tools import INFO_TOOLS, KNOWLEDGE_TOOLS, SEARCH_TOOLS
from src.skills.base_skill import BaseSkill

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool


class QASkill(BaseSkill):
    """常规智能问答智能体。"""

    id: str = "qa"
    name: str = "智能问答"
    description: str = (
        "面向日常问答任务的智能体：搜索、查询、快速回答用户问题。"
        "纯只读，不会修改文件或执行命令。"
    )

    # ---- 前端欢迎区的快捷提示卡 ----
    quick_prompts: list[dict[str, str]] = [
        {
            "icon": "HelpCircle",
            "title": "概念解释",
            "description": "一句话讲清",
            "prompt": "请用一句话解释什么是 AG-UI 协议，并对比 MCP 协议的主要差异。",
        },
        {
            "icon": "Calculator",
            "title": "算一算",
            "description": "小计算题",
            "prompt": "如果年化收益 6%，每月定投 2000 元，10 年后大概有多少？",
        },
        {
            "icon": "Globe",
            "title": "事实查询",
            "description": "最新信息",
            "prompt": "2026 年 1 月 1 日的 A 股大盘开盘情况如何？请给出当日涨跌幅与领涨板块。",
        },
        {
            "icon": "ListChecks",
            "title": "对比清单",
            "description": "两个选项",
            "prompt": "我想给团队选一个本地知识库工具，请对比 Obsidian、Notion、Logseq 的优劣。",
        },
    ]

    # ---- prompts ----
    planner_prompt: str = (
        "You are a QA planner.\n"
        "Analyze the user's question and create a concise plan. "
        "Output JSON: goal / steps / rationale. "
        "Steps should be minimal - most questions need only 1-2 search queries."
    )

    executor_prompt: str = (
        "You are a QA executor.\n"
        "Answer the user's question concisely and accurately. "
        "Cite your sources when using external information. "
        "If you're unsure, say so - do not make up answers."
    )

    reviewer_prompt: str = (
        "You are a QA reviewer.\n"
        "Audit the answer for: (1) accuracy, (2) completeness, (3) hallucination. "
        "Output JSON with verdict='approve' or 'revise'. "
        "If 'revise', name the specific issue in 'issues'."
    )

    @property
    def tools(self) -> list["BaseTool"]:
        """问答智能体的工具集 —— 搜索、知识、信息。"""
        return list(SEARCH_TOOLS) + list(KNOWLEDGE_TOOLS) + list(INFO_TOOLS)

    @property
    def hitl_rules(self) -> dict[str, dict[str, list[str]]]:
        """问答智能体 read-only，没有副作用，不需要任何审批门禁。"""
        return {}


__all__ = ["QASkill"]
