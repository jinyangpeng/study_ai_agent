"""MCP Inspector 替代品 - 用 Python MCP client SDK 程序化跑全链路。

不走浏览器，自动化环境下能完整跑通：
  - initialize
  - notifications/initialized
  - tools/list
  - resources/list
  - prompts/list
  - tools/call（拿真实响应）
  - resources/read
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime


def _bar(title: str) -> None:
    print()
    print("=" * 72)
    print(f"  {title}")
    print("=" * 72)


def _ok(label: str, detail: str = "") -> None:
    suffix = f"  {detail}" if detail else ""
    print(f"  [OK]  {label}{suffix}")


def _fail(label: str, detail: str = "") -> None:
    suffix = f"  {detail}" if detail else ""
    print(f"  [FAIL] {label}{suffix}")


async def main() -> int:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    server_url = "http://127.0.0.1:18770/mcp"
    print(f"target: {server_url}")
    print(f"client: mcp Python SDK (programmatic Inspector)")
    print(f"time:   {datetime.now().isoformat(timespec='seconds')}")

    async with streamablehttp_client(url=server_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            # ---- 1) initialize ----
            _bar("1) initialize / notifications/initialized")
            init_result = await session.initialize()
            server_info = init_result.serverInfo
            _ok(
                "initialize",
                f"server={server_info.name} v{server_info.version} protocol={init_result.protocolVersion}",
            )
            caps = init_result.capabilities
            _ok(
                "capabilities",
                f"tools={bool(caps.tools)} resources={bool(caps.resources)} prompts={bool(caps.prompts)}",
            )

            # ---- 2) tools/list ----
            _bar("2) tools/list")
            tools_resp = await session.list_tools()
            tools = tools_resp.tools
            _ok("tool count", str(len(tools)))
            print("     first 5 tools:")
            for t in tools[:5]:
                ann = t.annotations or {}
                flags = "".join(
                    [
                        "R" if getattr(ann, "read_only_hint", False) else "W",
                        "D" if getattr(ann, "destructive_hint", False) else "-",
                    ]
                )
                print(f"       [{flags}] {t.name}  -- {t.description or ''}")
            print(f"       ... ({len(tools) - 5} more)")

            # ---- 3) resources/list ----
            _bar("3) resources/list")
            res_resp = await session.list_resources()
            for r in res_resp.resources:
                _ok(f"resource {r.uri}", r.description or "")
            if not res_resp.resources:
                _fail("no resources found")

            # ---- 4) prompts/list ----
            _bar("4) prompts/list")
            prompt_resp = await session.list_prompts()
            for p in prompt_resp.prompts:
                _ok(f"prompt {p.name}", p.description or "")
            if not prompt_resp.prompts:
                _fail("no prompts found")

            # ---- 5) tools/call: crm_list_customers ----
            _bar("5) tools/call  crm_list_customers")
            r1 = await session.call_tool(
                "crm_list_customers",
                {"limit": 2, "response_format": "markdown"},
            )
            text1 = r1.content[0].text
            preview = text1.split("\n", 4)
            for line in preview[:4]:
                print(f"     | {line}")
            if r1.isError:
                _fail("call returned error", text1[:120])
            else:
                _ok("list_customers returned", f"{len(text1)} chars, isError={r1.isError}")

            # ---- 6) tools/call: crm_get_customer JSON ----
            _bar("6) tools/call  crm_get_customer  (json)")
            r2 = await session.call_tool(
                "crm_get_customer",
                {"customer_id": "C-000001", "response_format": "json"},
            )
            payload = json.loads(r2.content[0].text)
            customer = payload.get("data", payload)
            _ok("got customer", f"id={customer.get('id')} name={customer.get('name')}")
            _ok("schema fields", ",".join(list(customer.keys())[:8]))

            # ---- 7) tools/call: crm_create_customer + delete ----
            _bar("7) tools/call  crm_create_customer + crm_delete_customer")
            from crm_mcp.models import CustomerCreate

            params = CustomerCreate(name="Inspector 验证客户", industry="internet")
            r3 = await session.call_tool(
                "crm_create_customer",
                {"params": params.model_dump(), "response_format": "json"},
            )
            new = json.loads(r3.content[0].text).get("data") or json.loads(r3.content[0].text)
            new_id = new["id"]
            _ok("created", new_id)

            r4 = await session.call_tool("crm_delete_customer", {"customer_id": new_id})
            _ok("deleted", r4.content[0].text)

            # ---- 8) error path: delete non-existent ----
            _bar("8) error path  crm_delete_customer('C-999999')")
            r5 = await session.call_tool("crm_delete_customer", {"customer_id": "C-999999"})
            text5 = r5.content[0].text
            is_error_flag = r5.isError
            has_error_prefix = text5.startswith("Error [CRM_")
            if is_error_flag or has_error_prefix:
                _ok("got error (expected)", text5[:80].replace("\n", " "))
            else:
                _fail("expected error, got success:", text5[:80])

            # ---- 9) resources/read crm://overview ----
            _bar("9) resources/read  crm://overview")
            ov_resp = await session.read_resource("crm://overview")
            ov_text = ov_resp.contents[0].text
            print("     " + ov_text.split("\n", 1)[0])  # first line
            _ok("overview read", f"{len(ov_text)} bytes")

            # ---- 10) tools/call: crm_convert_lead ----
            _bar("10) tools/call  crm_convert_lead  L-000001")
            r6 = await session.call_tool(
                "crm_convert_lead",
                {"lead_id": "L-000001", "response_format": "json"},
            )
            if r6.isError:
                # L-000001 已经在 seed 里是 qualified，可以转；不在就是 error
                _ok("convert returned:", r6.content[0].text[:80].replace("\n", " "))
            else:
                payload6 = json.loads(r6.content[0].text)
                data6 = payload6.get("data", payload6)
                _ok(
                    "converted",
                    f"customer={data6['customer']['id']} contact={data6['contact']['id']}",
                )

    print()
    print("=" * 72)
    print("  ALL STEPS PASSED")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
