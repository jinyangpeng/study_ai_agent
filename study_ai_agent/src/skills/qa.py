"""QA Skill - 常规智能问答 Agent。

工具集
------
* Web 搜索、知识库、信息查询
* **MCP 集成工具**（:data:`INTEGRATION_TOOLS`）—— 外部 MCP 服务（如 CRM）
  的工具自动注入，LLM 在用户提问涉及相关领域时自动选用
* 核心工具集纯只读（不挂 FILE_TOOLS / SHELL_TOOLS）

HITL 策略
---------
MCP 写操作工具（create / update / delete / ...）自动纳入审批；
核心问答工具无副作用，不需要审批。
"""

# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.tools import INFO_TOOLS, INTEGRATION_TOOLS, KNOWLEDGE_TOOLS, SEARCH_TOOLS, get_integration_hitl_rules
from src.skills.base_skill import BaseSkill

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool


class QASkill(BaseSkill):
    """常规智能问答智能体。"""

    id: str = "qa"
    name: str = "智能问答"
    description: str = "面向日常问答任务的智能体：搜索、查询、快速回答用户问题。纯只读，不会修改文件或执行命令。"

    # 走Reflection
    strategy: str = "reflection"

    # 走 PERA：先规划答案要点，再执行（纯推理），最后 review 修正 —— 适合
    # 结构化、要点明确的问题。
    strategy: str = "p_e_r_a"

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

    # ---- Plan-Execute-Review-Act prompts ----
    plan_prompt: str = (
        "You are the PLAN node of a Plan-Execute-Review-Act agent.\n"
        "Analyze the user's question and create a concise plan. "
        "Output JSON: goal / steps / rationale. "
        "Steps should be minimal - most questions need only 1-2 search queries."
    )

    execute_prompt: str = (
        "You are the EXECUTE node of a Plan-Execute-Review-Act agent.\n"
        "Answer the user's question concisely and accurately. "
        "Cite your sources when using external information. "
        "If you're unsure, say so - do not make up answers."
    )

    review_prompt: str = (
        "You are the REVIEW node of a Plan-Execute-Review-Act agent.\n"
        "Audit the answer for: (1) accuracy, (2) completeness, (3) hallucination. "
        "Output JSON with verdict='approve' or 'revise'. "
        "If 'revise', name the specific issue in 'issues'."
    )

    @property
    def tools(self) -> list["BaseTool"]:
        """问答智能体的工具集 —— 搜索、知识、信息 + MCP 集成工具。"""
        return list(SEARCH_TOOLS) + list(KNOWLEDGE_TOOLS) + list(INFO_TOOLS) + list(INTEGRATION_TOOLS)

    @property
    def hitl_rules(self) -> dict[str, dict[str, list[str]]]:
        """MCP 写操作工具自动审批；核心问答工具无副作用不需要审批。"""
        return get_integration_hitl_rules()


__all__ = ["QASkill"]
