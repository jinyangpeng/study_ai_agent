"""Research skeleton - 资料调研 / 信息整合任务的 Agent。

工具集
------
* Web 搜索、知识库、计算、实时信息查询、安全工具
* **纯只读** - 不挂任何 FILE_TOOLS、SHELL_TOOLS、git 工具，
  execute 节点不会修改工作区。

HITL 策略
---------
空 dict —— read-only agent 没有副作用，所以不需要任何审批门禁。
前端可以把它跑成"无中断"模式。
"""
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.tools import (
    COMPUTATION_TOOLS,
    INFO_TOOLS,
    KNOWLEDGE_TOOLS,
    SAFETY_TOOLS,
    SEARCH_TOOLS,
)
from src.skills.base_skill import BaseSkill

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool


class ResearchSkill(BaseSkill):
    """深度研究智能体。"""

    id: str = "research"
    name: str = "深度研究智能体"
    description: str = (
        "面向研究 / 资料整合任务的智能体：搜索、抓取、阅读、引用、综合。"
        "纯只读，不会修改文件或执行命令。"
    )

    # 走 PERA：拆解 -> 检索 -> 审计（是否覆盖了所有子问题、引用是否可靠）。
    strategy: str = "p_e_r_a"

    # ---- 前端欢迎区的快捷提示卡 ----
    quick_prompts: list[dict[str, str]] = [
        {
            "icon": "Compass",
            "title": "LLM Agent 趋势",
            "description": "技术/应用/挑战",
            "prompt": "总结 2025 年 LLM Agent 的最新发展趋势，分技术、应用、挑战三部分。",
        },
        {
            "icon": "Search",
            "title": "对比综述",
            "description": "两家方案",
            "prompt": "对比 LangGraph 与 AutoGen 在多 Agent 编排上的设计理念与适用场景。",
        },
        {
            "icon": "BookOpen",
            "title": "找权威源",
            "description": "引文综述",
            "prompt": "请综述 RAG 领域的 5 篇关键论文（带发表年份与主要贡献）。",
        },
        {
            "icon": "FileText",
            "title": "快速摘要",
            "description": "一篇长文",
            "prompt": "帮我把注意力机制的核心思想用 200 字以内说清楚，并给出一个直观的类比。",
        },
    ]

    # ---- Plan-Execute-Review-Act prompts ----
    plan_prompt: str = (
        "You are the PLAN node of a Plan-Execute-Review-Act research agent.\n"
        "Turn the user's question into a research plan. Aim for 3-5 search queries\n"
        "that cover the topic from different angles (definition, evidence, counterpoint, recent updates).\n"
        "Output JSON: goal / steps / rationale. No tool calls."
    )

    execute_prompt: str = (
        "You are the EXECUTE node of a Plan-Execute-Review-Act research agent.\n"
        "For every claim you make, cite the URL you got it from. Use the Citation schema.\n"
        "Prefer authoritative sources (official docs, papers, primary news). "
        "Quote the exact passage you relied on.\n"
        "When the search returns no relevant result, state that explicitly - do not invent."
    )

    review_prompt: str = (
        "You are the REVIEW node of a Plan-Execute-Review-Act research agent.\n"
        "Audit the answer for: (1) unsupported claims, (2) circular citations, "
        "(3) missing counter-evidence, (4) staleness.\n"
        "Output JSON with verdict='approve' (publishable) or 'revise' (loop back).\n"
        "If 'revise', name the specific gap in 'issues'."
    )

    @property
    def tools(self) -> list["BaseTool"]:
        """研究智能体的工具集 —— 搜索、知识、计算、信息、安全。"""
        return (
            list(SEARCH_TOOLS)
            + list(KNOWLEDGE_TOOLS)
            + list(COMPUTATION_TOOLS)
            + list(INFO_TOOLS)
            + list(SAFETY_TOOLS)
        )

    @property
    def hitl_rules(self) -> dict[str, dict[str, list[str]]]:
        """研究智能体 read-only，没有副作用，不需要任何审批门禁。"""
        return {}


__all__ = ["ResearchSkill"]
