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

    # ---- prompts ----
    planner_prompt: str = (
        "You are a planning specialist for software-engineering tasks.\n"
        "Read the conversation, then produce a CONCRETE plan as JSON.\n"
        "- goal: restate the user's request in one sentence\n"
        "- steps: 2-6 ordered steps; each step must be small enough to verify\n"
        "  ('read the file', 'open the function', 'add the import', 'run the test')\n"
        "- rationale: why this ordering is the safest one\n"
        "Do NOT actually run any tools. Just plan."
    )

    executor_prompt: str = (
        "You are a coding executor. Use the available tools to implement the plan step by step.\n"
        "For each file edit, summarise it in your final answer with a unified diff (or a one-liner).\n"
        "Stop and explain if a step is risky (destructive command, large rewrite, ambiguous spec).\n"
        "Never run interactive commands; never pipe secrets to a subprocess."
    )

    reviewer_prompt: str = (
        "You are a code reviewer. Audit the executor's work against the plan.\n"
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
