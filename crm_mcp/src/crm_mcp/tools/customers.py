"""客户 (Customer) MCP 工具集。

工具命名规范 ``crm_<action>_<resource>``，避免与其它 MCP server 冲突。
"""

from __future__ import annotations

import logging
from typing import Any

from crm_mcp.enums import CustomerStatus, CustomerTier, Industry, ResponseFormat
from crm_mcp.formatters import (
    apply_filters,
    paginate,
    render_customer_md,
    render_response,
)
from crm_mcp.models import Customer, CustomerCreate, CustomerUpdate, ListQuery
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
    """注册 5 个客户相关工具到 FastMCP 实例。"""

    @mcp.tool(name="crm_list_customers", annotations=read_only_annotations("List customers"))
    @safe_tool_call
    async def crm_list_customers(
        query: str | None = None,
        status: CustomerStatus | None = None,
        tier: CustomerTier | None = None,
        industry: Industry | None = None,
        limit: int | None = None,
        offset: int = 0,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """按关键字 / 状态 / 分级 / 行业筛选客户，支持分页和排序。

        Args:
            query: 模糊匹配客户名 / 备注。
            status: 按客户状态过滤。
            tier: 按客户分级过滤。
            industry: 按行业过滤。
            limit: 分页大小（默认 20，最大 100）。
            offset: 分页偏移。
            sort_by: 排序字段（如 created_at / updated_at / name）。
            sort_order: ``asc`` / ``desc``。
            response_format: 返回 markdown 还是 json。

        Returns:
            渲染好的字符串。空结果返回 ``_没有匹配的记录。_``。
        """
        q = ListQuery(query=query, limit=limit, offset=offset, sort_by=sort_by, sort_order=sort_order)
        store = get_store()
        items = store.customers.list()
        items = apply_filters(
            items,
            query=q.query,
            status=status,
            extra_predicates=(
                lambda c: True if tier is None else c.tier == tier,
                lambda c: True if industry is None else c.industry == industry,
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
            item_render_md=render_customer_md,
            meta=meta,
            title="Customers",
        )

    @mcp.tool(name="crm_get_customer", annotations=read_only_annotations("Get a single customer"))
    @safe_tool_call
    async def crm_get_customer(
        customer_id: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """按 ID 获取客户详情。"""
        store = get_store()
        obj = store.customers.get(customer_id)
        return render_response(response_format, payload=obj)

    @mcp.tool(name="crm_create_customer", annotations=write_annotations("Create a customer"))
    @safe_tool_call
    async def crm_create_customer(
        params: CustomerCreate,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """创建客户，返回带 ID 的实体。"""
        store = get_store()
        new_id = store.customers.next_id()
        now = now_utc()
        obj = Customer(id=new_id, created_at=now, updated_at=now, **params.model_dump())
        await store.write_through(lambda: store.customers.add(obj))
        return render_response(response_format, payload=obj)

    @mcp.tool(name="crm_update_customer", annotations=write_annotations("Update a customer"))
    @safe_tool_call
    async def crm_update_customer(
        customer_id: str,
        params: CustomerUpdate,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """部分更新客户。未提供的字段保持不变。"""
        store = get_store()
        existing = store.customers.get(customer_id)
        updates = params.model_dump(exclude_unset=True)
        merged = existing.model_dump() | updates
        merged["updated_at"] = now_utc()
        new_obj = Customer.model_validate(merged)
        await store.write_through(lambda: store.customers.replace(new_obj))
        return render_response(response_format, payload=new_obj)

    @mcp.tool(
        name="crm_delete_customer",
        annotations=write_annotations("Delete a customer", destructive=True),
    )
    @safe_tool_call
    async def crm_delete_customer(customer_id: str) -> str:
        """删除客户；如有关联联系人/商机/活动会同时清理引用。"""
        store = get_store()
        store.customers.get(customer_id)  # 提前报 404

        def _txn() -> None:
            for c in list(store.contacts.list()):
                if c.customer_id == customer_id:
                    store.contacts.delete(c.id)
            for o in list(store.opportunities.list()):
                if o.customer_id == customer_id:
                    store.opportunities.delete(o.id)
            for a in list(store.activities.list()):
                if a.customer_id == customer_id:
                    store.activities.replace(a.model_copy(update={"customer_id": None}))
            store.customers.delete(customer_id)

        await store.write_through(_txn)
        return f"Customer `{customer_id}` deleted."


__all__ = ["register"]
