"""商机 (Opportunity) MCP 工具集。"""
from __future__ import annotations

import logging
from typing import Any

from crm_mcp.enums import OpportunityStage, Priority, ResponseFormat
from crm_mcp.formatters import (
    apply_filters,
    paginate,
    render_opportunity_md,
    render_response,
)
from crm_mcp.models import ListQuery, Opportunity, OpportunityCreate, OpportunityUpdate
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
    @mcp.tool(
        name="crm_list_opportunities",
        annotations=read_only_annotations("List opportunities"),
    )
    @safe_tool_call
    async def crm_list_opportunities(
        query: str | None = None,
        customer_id: str | None = None,
        stage: OpportunityStage | None = None,
        priority: Priority | None = None,
        owner: str | None = None,
        min_amount: float | None = None,
        limit: int | None = None,
        offset: int = 0,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """按客户 / 阶段 / 优先级 / 金额阈值筛选商机。

        Args:
            query: 模糊匹配名称 / 描述。
            customer_id: 仅返回该客户的商机。
            stage / priority: 精确过滤。
            owner: 按负责人过滤。
            min_amount: 最低金额（包含）。
            limit / offset: 分页。
            sort_by / sort_order: 排序。
            response_format: markdown | json。
        """
        q = ListQuery(query=query, limit=limit, offset=offset, sort_by=sort_by, sort_order=sort_order)
        store = get_store()
        items = store.opportunities.list()
        items = apply_filters(
            items,
            query=q.query,
            customer_id=customer_id,
            extra_predicates=(
                lambda o: True if stage is None else o.stage == stage,
                lambda o: True if priority is None else o.priority == priority,
                lambda o: True if owner is None else o.owner == owner,
                lambda o: True if min_amount is None else o.amount >= min_amount,
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
            item_render_md=render_opportunity_md,
            meta=meta,
            title="Opportunities",
        )

    @mcp.tool(
        name="crm_get_opportunity",
        annotations=read_only_annotations("Get a single opportunity"),
    )
    @safe_tool_call
    async def crm_get_opportunity(
        opportunity_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        store = get_store()
        obj = store.opportunities.get(opportunity_id)
        return render_response(response_format, payload=obj)

    @mcp.tool(
        name="crm_create_opportunity",
        annotations=write_annotations("Create an opportunity"),
    )
    @safe_tool_call
    async def crm_create_opportunity(
        params: OpportunityCreate,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        store = get_store()
        store.ensure_customer_exists(params.customer_id)
        if params.primary_contact_id:
            store.ensure_contact_exists(params.primary_contact_id)

        new_id = store.opportunities.next_id()
        now = now_utc()
        obj = Opportunity(id=new_id, created_at=now, updated_at=now, **params.model_dump())
        await store.write_through(lambda: store.opportunities.add(obj))
        return render_response(response_format, payload=obj)

    @mcp.tool(
        name="crm_update_opportunity",
        annotations=write_annotations("Update an opportunity"),
    )
    @safe_tool_call
    async def crm_update_opportunity(
        opportunity_id: str,
        params: OpportunityUpdate,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        store = get_store()
        existing = store.opportunities.get(opportunity_id)
        updates = params.model_dump(exclude_unset=True)
        if "customer_id" in updates:
            store.ensure_customer_exists(updates["customer_id"])
        if updates.get("primary_contact_id"):
            store.ensure_contact_exists(updates["primary_contact_id"])

        merged = existing.model_dump() | updates
        merged["updated_at"] = now_utc()
        new_obj = Opportunity.model_validate(merged)
        await store.write_through(lambda: store.opportunities.replace(new_obj))
        return render_response(response_format, payload=new_obj)

    @mcp.tool(
        name="crm_delete_opportunity",
        annotations=write_annotations("Delete an opportunity", destructive=True),
    )
    @safe_tool_call
    async def crm_delete_opportunity(opportunity_id: str) -> str:
        store = get_store()
        store.opportunities.get(opportunity_id)

        def _txn() -> None:
            for a in list(store.activities.list()):
                if a.opportunity_id == opportunity_id:
                    store.activities.replace(a.model_copy(update={"opportunity_id": None}))
            store.opportunities.delete(opportunity_id)

        await store.write_through(_txn)
        return f"Opportunity `{opportunity_id}` deleted."

    @mcp.tool(
        name="crm_advance_opportunity_stage",
        annotations=write_annotations("Move opportunity to a new stage"),
    )
    @safe_tool_call
    async def crm_advance_opportunity_stage(
        opportunity_id: str,
        new_stage: OpportunityStage,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """更新商机阶段。关闭（won/lost）时把 probability 强制置为 100/0。"""
        store = get_store()
        existing = store.opportunities.get(opportunity_id)
        updates: dict[str, Any] = {"stage": new_stage, "updated_at": now_utc()}
        if new_stage == OpportunityStage.CLOSED_WON:
            updates["probability"] = 100
        elif new_stage == OpportunityStage.CLOSED_LOST:
            updates["probability"] = 0
        new_obj = existing.model_copy(update=updates)
        await store.write_through(lambda: store.opportunities.replace(new_obj))
        return render_response(response_format, payload=new_obj)


__all__ = ["register"]
