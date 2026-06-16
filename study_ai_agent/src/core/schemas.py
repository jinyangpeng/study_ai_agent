"""所有智能体共用的结构化输出 schema。

这些 Pydantic 模型是 LangChain 1.x 子 agent（用
``create_agent(response_format=...)`` 构建）和外层 LangGraph state 之间的
类型安全契约。它们替代了之前 Pydantic-AI 运行时的 ``output_type=`` 体验 —
LangChain 1.x 通过 ``response_format=`` 产出同样的已校验 Pydantic 实例，
直接流入图的 typed state，无需自定义适配器。

智能体专属的 schema
--------------------
* ``Citation``  - 由 *research* 智能体产出（来源 URL、标题、节选）。
* ``CodeChange`` - 由 *coding* 智能体产出（文件路径、diff、说明）。

它们放在共享内核（而不是各自的智能体目录）里，是为了外层图 state 能把
``citations`` / ``code_changes`` 声明成可选字段，**任何** 智能体都可以填充。
不用的智能体就让它们保持空。
"""
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Plan 节点的结构化输出（Plan-Execute-Review-Act 架构的 P）
# ---------------------------------------------------------------------------
class PlanStep(BaseModel):
    """plan 节点输出中的单个有序步骤。

    plan 不会 *执行* 任何东西 —— 它只描述 execute 应该做什么。
    保持 schema 声明式（不绑定具体的 tool call），让同一份 :class:`Plan`
    既能驱动 LangChain execute 节点，也能驱动未来可能的 re-planning 循环。
    """

    id: str = Field(..., description="稳定的步骤标识（如 'step-1'）。")
    description: str = Field(..., description="execute 应该做什么。")
    expected_output: str = Field(
        default="", description="这一步成功的标志是什么。"
    )


class Plan(BaseModel):
    """plan 节点的结构化输出。

    由 plan 节点通过 ``create_agent(response_format=Plan)`` 产出，
    流入 :attr:`AgentState.plan`，execute 节点就能直接拿到类型化对象，
    不用再次解析自由文本。
    """

    goal: str = Field(..., description="用一句话重述用户的目标。")
    steps: list[PlanStep] = Field(default_factory=list)
    rationale: str = Field(
        default="", description="为什么这个方案是对的。"
    )


# ---------------------------------------------------------------------------
# Review 节点的结构化输出（Plan-Execute-Review-Act 架构的 R）
# ---------------------------------------------------------------------------
class Review(BaseModel):
    """review 节点的结构化输出。

    review 的 verdict 驱动 review 节点之后的那条条件边：
    ``approve`` -> act -> END，``revise`` -> 回 plan
    （由 LangGraph 的 ``recursion_limit`` 控制循环上限）。
    """

    verdict: Literal["approve", "revise"] = Field(
        ..., description="'approve' 表示发布，'revise' 表示回 plan 重新规划。"
    )
    issues: list[str] = Field(
        default_factory=list, description="execute 输出里发现的具体问题。"
    )
    suggestions: list[str] = Field(
        default_factory=list, description="下一轮应该做的具体修改。"
    )


class Critique(BaseModel):
    """reflection 策略的 critique 节点输出（架构的 C 步）。

    形状与 :class:`Review` 几乎一致 —— 都是二元 verdict + issues +
    suggestions；分开命名是因为它们的语义不同：

    * :class:`Review` 是 PERA 架构里"对照 plan 审计 execute 结果"的产物，
      关注"是否完成 plan / 是否合规范"。
    * :class:`Critique` 是 Reflection 架构里"对照原始问题评价当前 draft
      质量"的产物，关注"是否答得到位 / 是否能更准确更完整"。

    verdict 驱动 critique 之后的那条条件边：``approve`` -> act，``revise``
    -> refine（由 LangGraph 的 ``recursion_limit`` + skill 的
    ``max_reflection_iterations`` 兜底循环上限）。
    """

    verdict: Literal["approve", "revise"] = Field(
        ..., description="'approve' 表示发布，'revise' 表示回 refine 重写。"
    )
    issues: list[str] = Field(
        default_factory=list, description="当前 draft 里的具体问题。"
    )
    suggestions: list[str] = Field(
        default_factory=list, description="下一轮 refine 应该做的具体修改。"
    )


# ---------------------------------------------------------------------------
# 智能体专属（可选）的输出
# ---------------------------------------------------------------------------
class Citation(BaseModel):
    """由 *research* 智能体的 execute 节点产出的来源引用。

    execute 在系统 prompt 的引导下，每引用一个 web 抓取的事实都会附上
    :class:`Citation` 元数据。:class:`Citation` 对象流入
    :attr:`AgentState.citations`，作为侧信道数据暴露给 AG-UI 前端
    （例如 "References" 面板）。
    """

    url: str = Field(..., description="来源 URL。")
    title: str = Field(default="", description="页面或论文标题。")
    excerpt: str = Field(default="", description="支持该论断的引用节选。")
    accessed_at: str = Field(default="", description="访问的 ISO-8601 时间戳。")


class CodeChange(BaseModel):
    """由 *coding* 智能体的 execute 节点产出的文件编辑。

    execute 在系统 prompt 的引导下，每调用一次 ``write_file`` /
    ``edit_file`` 都会描述成一个 :class:`CodeChange` 条目，act
    节点据此可以渲染统一的 diff 摘要。
    """

    file: str = Field(..., description="文件路径（相对仓库根）。")
    diff: str = Field(default="", description="统一 diff 或一行摘要。")
    description: str = Field(default="", description="改了什么、为什么改。")


__all__ = ["Plan", "PlanStep", "Review", "Citation", "CodeChange"]
