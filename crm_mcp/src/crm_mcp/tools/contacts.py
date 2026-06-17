"""联系人 (Contact) MCP 工具集。"""
from __future__ import annotations

import logging
from typing import Any

from crm_mcp.enums import ContactRole, ResponseFormat
from crm_mcp.formatters import (
    apply_filters,
    paginate,
    render_contact_md,
    render_response,
)
from crm_mcp.models import Contact, ContactCreate, ContactUpdate, ListQuery
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
    @mcp.tool(name="crm_list_contacts", annotations=read_only_annotations("List contacts"))
    @safe_tool_call
    async def crm_list_contacts(
        query: str | None = None,
        customer_id: str | None = None,
        role: ContactRole | None = None,
        is_primary: bool | None = None,
        limit: int | None = None,
        offset: int = 0,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """按客户 / 角色 / 是否主联系人筛选联系人。

        Args:
            query: 模糊匹配姓名 / 邮箱 / 备注。
            customer_id: 仅返回指定客户的联系人。
            role: 按角色过滤（decision_maker / champion / user ...）。
            is_primary: True/False 仅返回主要联系人。
            limit / offset: 分页。
            sort_by / sort_order: 排序。
            response_format: markdown | json。
        """
        q = ListQuery(query=query, limit=limit, offset=offset, sort_by=sort_by, sort_order=sort_order)
        store = get_store()
        items = store.contacts.list()
        items = apply_filters(
            items,
            query=q.query,
            customer_id=customer_id,
            extra_predicates=(
                lambda c: True if role is None else c.role == role,
                lambda c: True if is_primary is None else c.is_primary == is_primary,
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
            item_render_md=render_contact_md,
            meta=meta,
            title="Contacts",
        )

    @mcp.tool(name="crm_get_contact", annotations=read_only_annotations("Get a single contact"))
    @safe_tool_call
    async def crm_get_contact(
        contact_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """按 ID 获取联系人详情。"""
        store = get_store()
        obj = store.contacts.get(contact_id)
        return render_response(response_format, payload=obj)

    @mcp.tool(name="crm_create_contact", annotations=write_annotations("Create a contact"))
    @safe_tool_call
    async def crm_create_contact(
        params: ContactCreate,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """创建联系人；会校验 customer_id 存在。"""
        store = get_store()
        store.ensure_customer_exists(params.customer_id)

        # 同客户下 is_primary=True 只能有一个，原子事务里把旧的降级
        new_id = store.contacts.next_id()
        now = now_utc()
        obj = Contact(id=new_id, created_at=now, updated_at=now, **params.model_dump())

        def _txn() -> None:
            if obj.is_primary:
                for c in store.contacts.list():
                    if c.customer_id == obj.customer_id and c.is_primary:
                        store.contacts.replace(
                            c.model_copy(update={"is_primary": False, "updated_at": now})
                        )
            store.contacts.add(obj)

        await store.write_through(_txn)
        return render_response(response_format, payload=obj)

    @mcp.tool(name="crm_update_contact", annotations=write_annotations("Update a contact"))
    @safe_tool_call
    async def crm_update_contact(
        contact_id: str,
        params: ContactUpdate,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """更新联系人；如果把 is_primary 置 True，会自动把同客户下其他联系人降级。"""
        store = get_store()
        existing = store.contacts.get(contact_id)
        updates = params.model_dump(exclude_unset=True)
        merged = existing.model_dump() | updates
        merged["updated_at"] = now_utc()

        if "customer_id" in updates:
            store.ensure_customer_exists(updates["customer_id"])
        if updates.get("is_primary") is True:
            target_customer = merged["customer_id"]
            for c in store.contacts.list():
                if (
                    c.id != contact_id
                    and c.customer_id == target_customer
                    and c.is_primary
                ):
                    store.contacts.replace(
                        c.model_copy(update={"is_primary": False, "updated_at": now_utc()})
                    )

        new_obj = Contact.model_validate(merged)
        await store.write_through(lambda: store.contacts.replace(new_obj))
        return render_response(response_format, payload=new_obj)

    @mcp.tool(
        name="crm_delete_contact",
        annotations=write_annotations("Delete a contact", destructive=True),
    )
    @safe_tool_call
    async def crm_delete_contact(contact_id: str) -> str:
        """删除联系人；活动里的引用会被置空。"""
        store = get_store()
        store.contacts.get(contact_id)

        def _txn() -> None:
            for a in list(store.activities.list()):
                if a.contact_id == contact_id:
                    store.activities.replace(a.model_copy(update={"contact_id": None}))
            store.contacts.delete(contact_id)

        await store.write_through(_txn)
        return f"Contact `{contact_id}` deleted."


__all__ = ["register"]
