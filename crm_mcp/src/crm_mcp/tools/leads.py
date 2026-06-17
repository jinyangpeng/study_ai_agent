"""销售线索 (Lead) MCP 工具集。"""
from __future__ import annotations

import logging
from typing import Any

from crm_mcp.enums import (
    ContactRole,
    CustomerStatus,
    Industry,
    LeadSource,
    LeadStatus,
    ResponseFormat,
)
from crm_mcp.formatters import (
    apply_filters,
    paginate,
    render_lead_md,
    render_response,
)
from crm_mcp.models import (
    Contact,
    Customer,
    Lead,
    LeadCreate,
    LeadUpdate,
    ListQuery,
)
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
    @mcp.tool(name="crm_list_leads", annotations=read_only_annotations("List leads"))
    @safe_tool_call
    async def crm_list_leads(
        query: str | None = None,
        status: LeadStatus | None = None,
        source: LeadSource | None = None,
        industry: Industry | None = None,
        owner: str | None = None,
        limit: int | None = None,
        offset: int = 0,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """按状态 / 来源 / 行业 / 负责人筛选线索。

        Args:
            query: 模糊匹配联系人 / 公司 / 备注。
            status / source / industry / owner: 精确过滤。
            limit / offset: 分页。
            sort_by / sort_order: 排序。
            response_format: markdown | json。
        """
        q = ListQuery(query=query, limit=limit, offset=offset, sort_by=sort_by, sort_order=sort_order)
        store = get_store()
        items = store.leads.list()
        items = apply_filters(
            items,
            query=q.query,
            status=status,
            extra_predicates=(
                lambda x: True if source is None else x.source == source,
                lambda x: True if industry is None else x.industry == industry,
                lambda x: True if owner is None else x.owner == owner,
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
            item_render_md=render_lead_md,
            meta=meta,
            title="Leads",
        )

    @mcp.tool(name="crm_get_lead", annotations=read_only_annotations("Get a single lead"))
    @safe_tool_call
    async def crm_get_lead(
        lead_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        store = get_store()
        obj = store.leads.get(lead_id)
        return render_response(response_format, payload=obj)

    @mcp.tool(name="crm_create_lead", annotations=write_annotations("Create a lead"))
    @safe_tool_call
    async def crm_create_lead(
        params: LeadCreate,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        store = get_store()
        new_id = store.leads.next_id()
        now = now_utc()
        obj = Lead(id=new_id, created_at=now, updated_at=now, **params.model_dump())
        await store.write_through(lambda: store.leads.add(obj))
        return render_response(response_format, payload=obj)

    @mcp.tool(name="crm_update_lead", annotations=write_annotations("Update a lead"))
    @safe_tool_call
    async def crm_update_lead(
        lead_id: str,
        params: LeadUpdate,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        store = get_store()
        existing = store.leads.get(lead_id)
        updates = params.model_dump(exclude_unset=True)
        merged = existing.model_dump() | updates
        merged["updated_at"] = now_utc()
        new_obj = Lead.model_validate(merged)
        await store.write_through(lambda: store.leads.replace(new_obj))
        return render_response(response_format, payload=new_obj)

    @mcp.tool(
        name="crm_delete_lead",
        annotations=write_annotations("Delete a lead", destructive=True),
    )
    @safe_tool_call
    async def crm_delete_lead(lead_id: str) -> str:
        """删除线索；活动里的引用置空。"""
        store = get_store()
        store.leads.get(lead_id)

        def _txn() -> None:
            for a in list(store.activities.list()):
                if a.lead_id == lead_id:
                    store.activities.replace(a.model_copy(update={"lead_id": None}))
            store.leads.delete(lead_id)

        await store.write_through(_txn)
        return f"Lead `{lead_id}` deleted."

    @mcp.tool(
        name="crm_convert_lead",
        annotations=write_annotations("Convert a lead to customer + contact"),
    )
    @safe_tool_call
    async def crm_convert_lead(
        lead_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """把合格线索转化为客户 + 主联系人，并把线索状态置为 converted。

        转化后：
        - 创建一个新客户（继承线索的公司/行业/预估价值备注）
        - 创建一个新联系人（继承线索的姓名/邮箱/电话/职位）
        - 线索 status → ``converted``，并记录 owner
        """
        store = get_store()
        lead = store.leads.get(lead_id)

        new_customer_id = store.customers.next_id()
        new_contact_id = store.contacts.next_id()
        now = now_utc()

        customer = Customer(
            id=new_customer_id,
            created_at=now,
            updated_at=now,
            name=lead.company,
            industry=lead.industry,
            tier="standard",
            status=CustomerStatus.PROSPECT,
            website=None,
            phone=lead.phone,
            address=None,
            annual_revenue=lead.estimated_value,
            employee_count=None,
            notes=f"由线索 {lead.id} 转化。{lead.notes or ''}".strip(),
            owner=lead.owner,
        )
        contact = Contact(
            id=new_contact_id,
            created_at=now,
            updated_at=now,
            customer_id=new_customer_id,
            full_name=lead.contact_name,
            title=lead.title,
            role=ContactRole.OTHER,
            email=lead.email,
            phone=lead.phone,
            linkedin=None,
            is_primary=True,
            notes="由线索转化而来。",
            owner=lead.owner,
        )
        updated_lead = lead.model_copy(update={"status": LeadStatus.CONVERTED, "updated_at": now})

        def _txn() -> None:
            store.customers.add(customer)
            store.contacts.add(contact)
            store.leads.replace(updated_lead)

        await store.write_through(_txn)

        payload = {
            "lead": updated_lead,
            "customer": customer,
            "contact": contact,
        }
        return render_response(response_format, payload=payload)


__all__ = ["register"]
