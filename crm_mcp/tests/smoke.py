"""Smoke test - 验证 CRM MCP 服务的关键路径。

不是单元测试套件；只用于冒烟（启动时跑一次确认 server 健康）。
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path


async def main() -> int:
    # 用临时目录作 data file，避免污染 seed
    tmp = Path(tempfile.mkdtemp(prefix="crm_mcp_smoke_"))
    os.environ["CRM_MCP_DATA_FILE"] = str(tmp / "store.json")
    os.environ["CRM_MCP_LOG_LEVEL"] = "WARNING"

    # 清掉 settings 的 lru_cache
    from crm_mcp import config as cfg

    cfg.get_settings.cache_clear()

    from crm_mcp.server import build_server

    mcp = build_server()
    tools = mcp._tool_manager._tools
    print(f"[1] tools registered: {len(tools)}")
    assert len(tools) == 28, f"expected 28 tools, got {len(tools)}"

    # 触发 lifespan 加载数据
    from crm_mcp.store import get_store

    store = get_store()
    await store.setup()
    print(f"[2] store loaded: customers={store.customers.count()} leads={store.leads.count()}")

    # 调用 list_customers
    list_tool = tools["crm_list_customers"]
    out = await list_tool.run({"limit": 2, "response_format": "json"})
    # FastMCP 的 tool.run() 返回值：通常就是 str；也可能是 list[TextContent]
    text = out[0].text if isinstance(out, list) else out
    payload = json.loads(text)
    assert payload["meta"]["total"] >= 5, payload
    assert len(payload["data"]) == 2
    print(f"[3] list_customers ok: total={payload['meta']['total']}")

    # 调用 get_customer
    out = await tools["crm_get_customer"].run({"customer_id": "C-000001", "response_format": "json"})
    text = out[0].text if isinstance(out, list) else out
    payload = json.loads(text)
    name = payload.get("data", {}).get("name") or payload.get("name", "")
    assert name.startswith("蓝芯"), name
    print(f"[4] get_customer ok: name={name}")

    # 资源（直接调用内部函数）
    resources = mcp._resource_manager._resources
    res = resources["crm://overview"]
    out = await res.fn()
    text = out[0].text if isinstance(out, list) else out
    assert "客户" in text
    print(f"[5] resource crm://overview ok ({len(text)} bytes)")

    # 创建一个新客户
    from crm_mcp.models import CustomerCreate

    new_payload = CustomerCreate(name="烟雾测试客户", industry="internet").model_dump()
    out = await tools["crm_create_customer"].run({"params": new_payload, "response_format": "json"})
    text = out[0].text if isinstance(out, list) else out
    payload = json.loads(text)
    new_id = (payload.get("data") or payload).get("id")
    assert new_id and new_id.startswith("C-"), new_id
    print(f"[6] create_customer ok: new id={new_id}")

    # 删除
    out = await tools["crm_delete_customer"].run({"customer_id": new_id})
    text = out[0].text if isinstance(out, list) else out
    assert "deleted" in text.lower()
    print(f"[7] delete_customer ok: {text}")

    # 错误路径：删除不存在的客户
    out = await tools["crm_delete_customer"].run({"customer_id": "C-999999"})
    text = out[0].text if isinstance(out, list) else out
    assert "not found" in text.lower() or "NOT_FOUND" in text, text
    print(f"[8] error path ok: {text[:60]}...")

    print()
    print("ALL SMOKE TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
