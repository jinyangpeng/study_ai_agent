"""跟进活动 (Activity) MCP 工具集。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from crm_mcp.enums import ActivityStatus, ActivityType, ResponseFormat
from crm_mcp.formatters import (
    apply_filters,
    paginate,
    render_activity_md,
    render_response,
)
from crm_mcp.models import Activity, ActivityCreate, ActivityUpdate, ListQuery
from crm_mcp.store import get_store
from crm_mcp.tools._common import (
    now_utc,
    read_only_annotations,
    resolve_page_size,
    safe_tool_call,
    write_annotations,
)

logger = logging.getLogger(__name__)


def register(mcp: Any) -> None:
    @mcp.tool(name="crm_list_activities", annotations=read_only_annotations("List activities"))
    @safe_tool_call
    async def crm_list_activities(
        query: str | None = None,
        status: ActivityStatus | None = None,
        activity_type: ActivityType | None = None,
        customer_id: str | None = None,
        contact_id: str | None = None,
        lead_id: str | None = None,
        opportunity_id: str | None = None,
        owner: str | None = None,
        due_before: datetime | None = None,
        limit: int | None = None,
        offset: int = 0,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """按多维条件筛选活动。

        Args:
            query: 模糊匹配主题 / 描述。
            status / activity_type: 精确过滤。
            customer_id / contact_id / lead_id / opportunity_id: 关联实体过滤。
            owner: 负责人过滤。
            due_before: 仅返回截止时间早于该时刻的活动（用于"找过期待办"）。
            limit / offset: 分页。
            sort_by / sort_order: 排序。
            response_format: markdown | json。
        """
        q = ListQuery(query=query, limit=limit, offset=offset, sort_by=sort_by, sort_order=sort_order)
        store = get_store()
        items = store.activities.list()
        items = apply_filters(
            items,
            query=q.query,
            status=status,
            customer_id=customer_id,
            extra_predicates=(
                lambda a: True if activity_type is None else a.activity_type == activity_type,
                lambda a: True if contact_id is None else a.contact_id == contact_id,
                lambda a: True if lead_id is None else a.lead_id == lead_id,
                lambda a: True if opportunity_id is None else a.opportunity_id == opportunity_id,
                lambda a: True if owner is None else a.owner == owner,
                lambda a: True if due_before is None else (a.due_at is not None and a.due_at < due_before),
            ),
        )
        items = sorted(
            items,
            key=lambda c: getattr(c, q.sort_by or "updated_at", "") or "",
            reverse=(q.sort_order or "desc").lower() != "asc",
        )
        off, lim = resolve_page_size(q)
        page, meta = paginate(items, offset=off, limit=lim)
        return render_response(
            response_format,
            items=page,
            item_render_md=render_activity_md,
            meta=meta,
            title="Activities",
        )

    @mcp.tool(name="crm_get_activity", annotations=read_only_annotations("Get a single activity"))
    @safe_tool_call
    async def crm_get_activity(
        activity_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        store = get_store()
        obj = store.activities.get(activity_id)
        return render_response(response_format, payload=obj)

    @mcp.tool(name="crm_create_activity", annotations=write_annotations("Create an activity"))
    @safe_tool_call
    async def crm_create_activity(
        params: ActivityCreate,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """创建活动。会自动校验所有外键（customer/contact/lead/opportunity）。"""
        store = get_store()
        if params.customer_id:
            store.ensure_customer_exists(params.customer_id)
        if params.contact_id:
            store.ensure_contact_exists(params.contact_id)
        if params.lead_id:
            store.ensure_lead_exists(params.lead_id)
        if params.opportunity_id:
            store.ensure_opportunity_exists(params.opportunity_id)

        new_id = store.activities.next_id()
        now = now_utc()
        obj = Activity(id=new_id, created_at=now, updated_at=now, **params.model_dump())

        # 状态完成时自动设置 completed_at
        if obj.status == ActivityStatus.COMPLETED and obj.completed_at is None:
            obj = obj.model_copy(update={"completed_at": now})

        await store.write_through(lambda: store.activities.add(obj))
        return render_response(response_format, payload=obj)

    @mcp.tool(name="crm_update_activity", annotations=write_annotations("Update an activity"))
    @safe_tool_call
    async def crm_update_activity(
        activity_id: str,
        params: ActivityUpdate,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        store = get_store()
        existing = store.activities.get(activity_id)
        updates = params.model_dump(exclude_unset=True)

        for fk in ("customer_id", "contact_id", "lead_id", "opportunity_id"):
            if fk in updates and updates[fk] is not None:
                getattr(store, f"ensure_{fk.split('_')[0]}_exists")(updates[fk])

        merged = existing.model_dump() | updates
        merged["updated_at"] = now_utc()
        # 转 completed 时自动写完成时间
        if merged.get("status") == ActivityStatus.COMPLETED and not merged.get("completed_at"):
            merged["completed_at"] = now_utc()
        new_obj = Activity.model_validate(merged)
        await store.write_through(lambda: store.activities.replace(new_obj))
        return render_response(response_format, payload=new_obj)

    @mcp.tool(
        name="crm_delete_activity",
        annotations=write_annotations("Delete an activity", destructive=True),
    )
    @safe_tool_call
    async def crm_delete_activity(activity_id: str) -> str:
        store = get_store()
        store.activities.get(activity_id)
        await store.write_through(lambda: store.activities.delete(activity_id))
        return f"Activity `{activity_id}` deleted."

    @mcp.tool(
        name="crm_complete_activity",
        annotations=write_annotations("Mark an activity as completed"),
    )
    @safe_tool_call
    async def crm_complete_activity(
        activity_id: str,
        notes: str | None = None,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """把活动标记为已完成，自动写入 completed_at。"""
        store = get_store()
        existing = store.activities.get(activity_id)
        now = now_utc()
        updates: dict[str, Any] = {
            "status": ActivityStatus.COMPLETED,
            "completed_at": now,
            "updated_at": now,
        }
        if notes is not None:
            updates["description"] = (
                (existing.description or "") + f"\n\n[{now.isoformat(timespec='seconds')}] {notes}"
            ).strip()
        new_obj = existing.model_copy(update=updates)
        await store.write_through(lambda: store.activities.replace(new_obj))
        return render_response(response_format, payload=new_obj)


__all__ = ["register"]
