"""Coding Skill - 软件工程任务智能体。

工具集
------
* 文件读写 / 搜索（:data:`FILE_TOOLS` + :data:`SEARCH_TOOLS`）
* 现实部署会把这些换成具体的 bash、git、IDE wrapper。

HITL 策略
---------
六个会改变文件系统 / git 状态、调用 shell 的工具都做了审批门禁。
``write_file`` / ``edit_file`` 允许 ``edit``（人工调整内容后批准），
``delete_file`` / ``shell_exec`` / ``git_commit`` / ``git_push`` 只允许
``approve`` / ``reject``（partial edit 太危险）。
"""
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.tools import FILE_TOOLS, SEARCH_TOOLS
from src.skills.base_skill import BaseSkill

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool


class CodingSkill(BaseSkill):
    """编程智能体。"""

    id: str = "coding"
    name: str = "编程智能体"
    description: str = (
        "面向软件工程任务的智能体：读取 / 搜索 / 编辑文件，运行命令，提交代码。"
        "写文件和 shell 命令会触发人工审批。"
    )

    # ---- 前端欢迎区的快捷提示卡 ----
    quick_prompts: list[dict[str, str]] = [
        {
            "icon": "Code2",
            "title": "LRU 缓存",
            "description": "带完整测试",
            "prompt": "帮我用 Python 实现一个 LRU 缓存，要求有完整的测试用例。",
        },
        {
            "icon": "BookOpen",
            "title": "代码解读",
            "description": "理解项目结构",
            "prompt": "请解释当前项目 src/core 目录下的核心模块职责。",
        },
        {
            "icon": "Lightbulb",
            "title": "功能设计",
            "description": "给一组需求",
            "prompt": "给一个 AI Agent 产品设计 5 个差异化的核心功能。",
        },
        {
            "icon": "Wrench",
            "title": "Bug 排查",
            "description": "贴异常栈分析",
            "prompt": "分析下面这段 Python 报错的根因，并给出最小修复 patch：\n```\nTraceback ...\n```",
        },
    ]

    # ---- Plan-Execute-Review-Act prompts ----
    plan_prompt: str = (
        "You are the PLAN node of a Plan-Execute-Review-Act coding agent.\n"
        "Read the conversation, then produce a CONCRETE plan as JSON.\n"
        "- goal: restate the user's request in one sentence\n"
        "- steps: 2-6 ordered steps; each step must be small enough to verify\n"
        "  ('read the file', 'open the function', 'add the import', 'run the test')\n"
        "- rationale: why this ordering is the safest one\n"
        "Do NOT actually run any tools. Just plan."
    )

    execute_prompt: str = (
        "You are the EXECUTE node of a Plan-Execute-Review-Act coding agent. "
        "Use the available tools to implement the plan step by step.\n"
        "For each file edit, summarise it in your final answer with a unified diff (or a one-liner).\n"
        "Stop and explain if a step is risky (destructive command, large rewrite, ambiguous spec).\n"
        "Never run interactive commands; never pipe secrets to a subprocess."
    )

    review_prompt: str = (
        "You are the REVIEW node of a Plan-Execute-Review-Act coding agent. "
        "Audit the execute node's work against the plan.\n"
        "Output JSON with verdict='approve' (publishable) or 'revise' (loop back).\n"
        "Be specific in 'issues' and 'suggestions' - vague feedback is not actionable."
    )

    @property
    def tools(self) -> list["BaseTool"]:
        """编程智能体的工具集 —— 文件 + 代码搜索。"""
        return list(FILE_TOOLS) + list(SEARCH_TOOLS)

    @property
    def hitl_rules(self) -> dict[str, dict[str, list[str]]]:
        """对变更类工具的 HITL 闸门。"""
        return {
            "write_file": {"allowed_decisions": ["approve", "edit", "reject"]},
            "edit_file": {"allowed_decisions": ["approve", "edit", "reject"]},
            "delete_file": {"allowed_decisions": ["approve", "reject"]},
            "shell_exec": {"allowed_decisions": ["approve", "edit", "reject"]},
            "git_commit": {"allowed_decisions": ["approve", "reject"]},
            "git_push": {"allowed_decisions": ["approve", "reject"]},
        }


__all__ = ["CodingSkill"]
