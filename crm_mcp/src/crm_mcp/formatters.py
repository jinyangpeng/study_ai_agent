"""响应格式化器 - 把 Pydantic 模型渲染为 JSON 或 Markdown。

MCP 工具默认返回 ``str``，由 LLM 消费。Markdown 适合人读 / 简单 LLM 提示；
JSON 适合"模型→代码"二次处理。本模块集中做这件事，避免在每个 tool 里散落。
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Iterable, Sequence

from pydantic import BaseModel

from crm_mcp.enums import ResponseFormat
from crm_mcp.models import (
    Activity,
    Contact,
    Customer,
    Lead,
    Opportunity,
)


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------
def to_json(obj: Any) -> str:
    """统一 JSON 序列化（带缩进，确保中文不转义）。"""
    return json.dumps(obj, ensure_ascii=False, indent=2, default=_json_default)


def _json_default(o: Any) -> Any:
    if isinstance(o, datetime):
        return o.isoformat()
    if hasattr(o, "model_dump"):
        return o.model_dump(mode="json")
    # Enum instances: 优先用 value（"active"）而不是类名（"CustomerStatus.ACTIVE"）
    if hasattr(o, "value"):
        return o.value
    return str(o)


def _enum_value(v: Any) -> str:
    """Pydantic Enum / 普通值 → 字符串。用于 Markdown 渲染。"""
    if v is None:
        return "—"
    if hasattr(v, "value"):
        return str(v.value)
    return str(v)


# ---------------------------------------------------------------------------
# 列表 + 分页
# ---------------------------------------------------------------------------
def paginate(
    items: Sequence[Any],
    *,
    offset: int,
    limit: int,
) -> tuple[list[Any], dict[str, Any]]:
    """分页切片，返回 (本页 items, 摘要元数据)。"""
    total = len(items)
    page = items[offset : offset + limit]
    has_more = offset + len(page) < total
    next_offset = offset + len(page) if has_more else None
    meta = {
        "total": total,
        "count": len(page),
        "offset": offset,
        "limit": limit,
        "has_more": has_more,
        "next_offset": next_offset,
    }
    return list(page), meta


def apply_filters(
    items: Iterable[Customer] | Iterable[Contact] | Iterable[Lead] | Iterable[Opportunity] | Iterable[Activity],
    *,
    query: str | None = None,
    status: Any = None,
    customer_id: str | None = None,
    extra_predicates: Sequence[Any] = (),
) -> list[Any]:
    """通用过滤：关键字 + 状态/外键 + 自定义断言。"""
    out: list[Any] = []
    for it in items:
        if status is not None and getattr(it, "status", None) != status:
            continue
        if customer_id is not None and getattr(it, "customer_id", None) != customer_id:
            continue
        if query:
            haystack = _searchable_text(it)
            if query.lower() not in haystack.lower():
                continue
        if all(p(it) for p in extra_predicates):
            out.append(it)
    return out


def _searchable_text(it: Any) -> str:
    """聚合可搜索字段。"""
    fields: list[str] = []
    for attr in ("name", "subject", "full_name", "contact_name", "company", "notes", "description"):
        v = getattr(it, attr, None)
        if v:
            fields.append(str(v))
    return " | ".join(fields)


# ---------------------------------------------------------------------------
# Markdown 渲染
# ---------------------------------------------------------------------------
def _fmt_dt(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    return dt.strftime("%Y-%m-%d %H:%M")


def render_customer_md(c: Customer) -> str:
    return (
        f"### {c.name} (`{c.id}`)\n"
        f"- **状态**: {_enum_value(c.status)} | **分级**: {_enum_value(c.tier)} | "
        f"**行业**: {_enum_value(c.industry)}\n"
        f"- **负责人**: {c.owner or '—'}\n"
        f"- **官网**: {c.website or '—'} | **电话**: {c.phone or '—'}\n"
        f"- **地址**: {c.address or '—'}\n"
        f"- **年收入**: {c.annual_revenue or '—'} 元 | **员工数**: {c.employee_count or '—'}\n"
        f"- **创建**: {_fmt_dt(c.created_at)} | **更新**: {_fmt_dt(c.updated_at)}\n"
        + (f"- **备注**: {c.notes}\n" if c.notes else "")
    )


def render_contact_md(co: Contact) -> str:
    return (
        f"### {co.full_name} (`{co.id}`)\n"
        f"- **所属客户**: `{co.customer_id}` | **角色**: {_enum_value(co.role)}\n"
        f"- **职位**: {co.title or '—'}\n"
        f"- **邮箱**: {co.email or '—'} | **电话**: {co.phone or '—'}\n"
        f"- **主要联系人**: {'是' if co.is_primary else '否'}\n"
        f"- **负责人**: {co.owner or '—'}\n" + (f"- **备注**: {co.notes}\n" if co.notes else "")
    )


def render_lead_md(lead: Lead) -> str:
    return (
        f"### {lead.contact_name} @ {lead.company} (`{lead.id}`)\n"
        f"- **状态**: {_enum_value(lead.status)} | **来源**: {_enum_value(lead.source)} | "
        f"**行业**: {_enum_value(lead.industry)}\n"
        f"- **职位**: {lead.title or '—'}\n"
        f"- **邮箱**: {lead.email or '—'} | **电话**: {lead.phone or '—'}\n"
        f"- **预估价值**: {lead.estimated_value or '—'} 元\n"
        f"- **负责人**: {lead.owner or '—'}\n"
        f"- **创建**: {_fmt_dt(lead.created_at)} | **更新**: {_fmt_dt(lead.updated_at)}\n"
        + (f"- **备注**: {lead.notes}\n" if lead.notes else "")
    )


def render_opportunity_md(o: Opportunity) -> str:
    return (
        f"### {o.name} (`{o.id}`)\n"
        f"- **客户**: `{o.customer_id}` | **联系人**: {o.primary_contact_id or '—'}\n"
        f"- **阶段**: {_enum_value(o.stage)} | **优先级**: {_enum_value(o.priority)} | "
        f"**赢率**: {o.probability}%\n"
        f"- **金额**: {o.amount} {o.currency} | **预计成交**: {_fmt_dt(o.expected_close_date)}\n"
        f"- **负责人**: {o.owner or '—'}\n"
        f"- **创建**: {_fmt_dt(o.created_at)} | **更新**: {_fmt_dt(o.updated_at)}\n"
        + (f"- **描述**: {o.description}\n" if o.description else "")
    )


def render_activity_md(a: Activity) -> str:
    return (
        f"### {a.subject} (`{a.id}`)\n"
        f"- **类型**: {_enum_value(a.activity_type)} | **状态**: {_enum_value(a.status)}\n"
        f"- **关联**: customer={a.customer_id or '—'} | contact={a.contact_id or '—'} | "
        f"lead={a.lead_id or '—'} | opportunity={a.opportunity_id or '—'}\n"
        f"- **截止**: {_fmt_dt(a.due_at)} | **完成**: {_fmt_dt(a.completed_at)}\n"
        f"- **负责人**: {a.owner or '—'}\n"
        f"- **创建**: {_fmt_dt(a.created_at)}\n" + (f"\n{a.description}\n" if a.description else "")
    )


def render_overview_md(stats: dict[str, Any]) -> str:
    """把 store.overview() 渲染成易读的概览。"""
    lines: list[str] = ["# CRM 数据概览", ""]

    c = stats["customers"]
    lines.append("## 客户")
    lines.append(f"- 总数: **{c['total']}**")
    if c["by_status"]:
        lines.append("- 按状态: " + ", ".join(f"{k}={v}" for k, v in c["by_status"].items()))
    if c["by_tier"]:
        lines.append("- 按分级: " + ", ".join(f"{k}={v}" for k, v in c["by_tier"].items()))
    lines.append("")

    co = stats["contacts"]
    lines.append("## 联系人")
    lines.append(f"- 总数: **{co['total']}** (主要: {co['primary']})")
    lines.append("")

    leads_stats = stats["leads"]
    lines.append("## 销售线索")
    lines.append(f"- 总数: **{leads_stats['total']}**")
    if leads_stats["by_status"]:
        lines.append("- 按状态: " + ", ".join(f"{k}={v}" for k, v in leads_stats["by_status"].items()))
    lines.append("")

    o = stats["opportunities"]
    lines.append("## 商机")
    lines.append(f"- 总数: **{o['total']}** | 管线价值: **{o['pipeline_value']}** 元")
    if o["by_stage"]:
        lines.append("- 按阶段: " + ", ".join(f"{k}={v}" for k, v in o["by_stage"].items()))
    lines.append("")

    a = stats["activities"]
    lines.append("## 活动")
    lines.append(f"- 总数: **{a['total']}**")
    if a["by_status"]:
        lines.append("- 按状态: " + ", ".join(f"{k}={v}" for k, v in a["by_status"].items()))
    if a["by_type"]:
        lines.append("- 按类型: " + ", ".join(f"{k}={v}" for k, v in a["by_type"].items()))
    return "\n".join(lines) + "\n"


def render_list_md(
    title: str,
    items_md: Sequence[str],
    meta: dict[str, Any],
) -> str:
    """列表响应：标题 + 分页摘要 + 各条目 Markdown 块。"""
    header = f"## {title} (total={meta['total']}, count={meta['count']}, offset={meta['offset']}, limit={meta['limit']}"
    if meta.get("has_more"):
        header += f", next_offset={meta['next_offset']}"
    header += ")"
    if not items_md:
        return f"{header}\n\n_没有匹配的记录。_"
    return header + "\n\n" + "\n\n---\n\n".join(items_md) + "\n"


# ---------------------------------------------------------------------------
# 错误格式化
# ---------------------------------------------------------------------------
def format_error(exc: Exception) -> str:
    """统一的错误消息格式。"""
    from crm_mcp.errors import CRMError

    if isinstance(exc, CRMError):
        base = f"Error [{exc.code}]: {exc.message}"
        if exc.hint:
            base += f"\nHint: {exc.hint}"
        return base
    return f"Error [UNEXPECTED]: {type(exc).__name__}: {exc}"


def render_response(
    fmt: ResponseFormat,
    *,
    items: Sequence[BaseModel] | None = None,
    item_render_md=None,
    meta: dict[str, Any] | None = None,
    title: str = "Results",
    payload: Any = None,
) -> str:
    """统一调度：JSON / Markdown。

    - 列表场景：传 ``items`` + ``item_render_md`` + ``meta`` + ``title``。
    - 单对象场景：传 ``payload``（dict / 模型均可）。
    """
    if fmt == ResponseFormat.JSON:
        if payload is not None:
            if hasattr(payload, "model_dump"):
                payload = payload.model_dump(mode="json")
            data = payload
            if meta:
                data = {"meta": meta, "data": payload}
            return to_json(data)
        assert items is not None and meta is not None
        return to_json(
            {
                "meta": meta,
                "data": [it.model_dump(mode="json") if hasattr(it, "model_dump") else it for it in items],
            }
        )

    # markdown
    if payload is not None:
        if hasattr(payload, "model_dump"):
            return "```json\n" + to_json(payload.model_dump(mode="json")) + "\n```\n"
        if isinstance(payload, BaseModel):
            return "```json\n" + to_json(payload.model_dump(mode="json")) + "\n```\n"
        return "```json\n" + to_json(payload) + "\n```\n"

    assert items is not None and meta is not None and item_render_md is not None
    blocks = [item_render_md(it) for it in items]
    return render_list_md(title, blocks, meta)


__all__ = [
    "to_json",
    "paginate",
    "apply_filters",
    "render_customer_md",
    "render_contact_md",
    "render_lead_md",
    "render_opportunity_md",
    "render_activity_md",
    "render_overview_md",
    "render_list_md",
    "render_response",
    "format_error",
]
