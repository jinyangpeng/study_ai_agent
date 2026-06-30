"""MCP 集成工具测试。

覆盖：
1. _parse_servers() 配置解析
2. _is_write_tool() 写操作识别（CRM + 任意未来 MCP 服务）
3. get_integration_hitl_rules() HITL 规则自动生成
4. 三个 skill 都注入了 INTEGRATION_TOOLS
5. reload() 热重载机制

跑法（项目根）::

    python tests/manual/smoke_mcp_integration.py

或用 pytest::

    pytest tests/manual/smoke_mcp_integration.py -v
"""
# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from pathlib import Path

# Ensure the project root is importable
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Mock tool —— 模拟 langchain BaseTool 的最小替身
# ---------------------------------------------------------------------------
class MockTool:
    """模拟 langchain BaseTool，用于测试 _is_write_tool。"""

    def __init__(self, name: str, metadata: dict | None = None):
        self.name = name
        self.metadata = metadata or {}

    def __repr__(self):
        return f"MockTool({self.name!r})"


# ---------------------------------------------------------------------------
# 测试 1: _parse_servers
# ---------------------------------------------------------------------------
def test_parse_servers():
    from src.core.tools.integration_tools import _parse_servers

    # 单 server
    result = _parse_servers("crm=http://localhost:8001/mcp")
    assert result == {"crm": {"url": "http://localhost:8001/mcp", "transport": "streamable_http"}}
    print("[OK] 单 server 解析正确")

    # 多 server
    result = _parse_servers("crm=http://localhost:8001/mcp,ticket=http://localhost:9000/mcp")
    assert len(result) == 2
    assert "crm" in result
    assert "ticket" in result
    print("[OK] 多 server 解析正确")

    # 空配置
    assert _parse_servers("") == {}
    assert _parse_servers("   ") == {}
    print("[OK] 空配置返回空 dict")

    # 带空格
    result = _parse_servers(" crm = http://localhost:8001/mcp , ticket = http://localhost:9000/mcp ")
    assert len(result) == 2
    print("[OK] 带空格配置正确 trim")

    # 无效条目跳过
    result = _parse_servers("crm=http://localhost:8001/mcp,invalid_entry,=no_url")
    assert len(result) == 1
    assert "crm" in result
    print("[OK] 无效条目被跳过")


# ---------------------------------------------------------------------------
# 测试 2: _is_write_tool
# ---------------------------------------------------------------------------
def test_is_write_tool():
    from src.core.tools.integration_tools import _is_write_tool

    # --- CRM 读操作（应返回 False）---
    crm_read_tools = [
        "crm_list_customers", "crm_get_customer",
        "crm_list_contacts", "crm_get_contact",
        "crm_list_leads", "crm_get_lead",
        "crm_list_activities", "crm_get_activity",
        "crm_list_opportunities", "crm_get_opportunity",
    ]
    for name in crm_read_tools:
        assert not _is_write_tool(MockTool(name)), f"{name} 不应被判定为写操作"
    print(f"[OK] {len(crm_read_tools)} 个 CRM 读操作正确识别为非写操作")

    # --- CRM 写操作（应返回 True）---
    crm_write_tools = [
        "crm_create_customer", "crm_update_customer", "crm_delete_customer",
        "crm_create_contact", "crm_update_contact", "crm_delete_contact",
        "crm_create_lead", "crm_update_lead", "crm_delete_lead", "crm_convert_lead",
        "crm_create_activity", "crm_update_activity", "crm_delete_activity", "crm_complete_activity",
        "crm_create_opportunity", "crm_update_opportunity", "crm_delete_opportunity", "crm_advance_opportunity_stage",
    ]
    for name in crm_write_tools:
        assert _is_write_tool(MockTool(name)), f"{name} 应被判定为写操作"
    print(f"[OK] {len(crm_write_tools)} 个 CRM 写操作正确识别为写操作")

    # --- 未来 MCP 服务的工具名（零代码扩展验证）---
    future_write_tools = [
        "ticket_create", "ticket_update", "ticket_delete",
        "order_cancel", "order_submit",
        "invoice_send", "invoice_archive",
        "user_deactivate", "user_activate",
        "task_assign", "task_transfer",
        "project_close", "project_merge",
        "campaign_advance", "campaign_restore",
    ]
    for name in future_write_tools:
        assert _is_write_tool(MockTool(name)), f"未来工具 {name} 应被判定为写操作"
    print(f"[OK] {len(future_write_tools)} 个未来 MCP 写操作自动识别")

    future_read_tools = ["ticket_list", "ticket_get", "order_status", "report_view", "stats_get", "user_profile"]
    for name in future_read_tools:
        assert not _is_write_tool(MockTool(name)), f"未来工具 {name} 不应被判定为写操作"
    print(f"[OK] {len(future_read_tools)} 个未来 MCP 读操作自动识别为非写操作")

    # --- MCP annotations 优先级 ---
    # readOnlyHint=True → 即使名字含 create 也返回 False
    tool = MockTool("crm_create_customer", metadata={"annotations": {"readOnlyHint": True}})
    assert not _is_write_tool(tool), "readOnlyHint=True 应覆盖名字匹配"
    print("[OK] readOnlyHint annotation 优先于名字匹配")

    # destructiveHint=True → 即使名字不含关键词也返回 True
    tool = MockTool("crm_query_data", metadata={"annotations": {"destructiveHint": True}})
    assert _is_write_tool(tool), "destructiveHint=True 应触发写操作判定"
    print("[OK] destructiveHint annotation 优先于名字匹配")


# ---------------------------------------------------------------------------
# 测试 3: get_integration_hitl_rules
# ---------------------------------------------------------------------------
def test_get_integration_hitl_rules():
    from src.core.tools.integration_tools import INTEGRATION_TOOLS, get_integration_hitl_rules

    # 当前 INTEGRATION_TOOLS 可能为空（MCP server 未启动），先验证空情况
    rules = get_integration_hitl_rules()
    assert isinstance(rules, dict)
    print(f"[OK] 当前 MCP 工具数: {len(INTEGRATION_TOOLS)}, HITL 规则数: {len(rules)}")

    # 用 mock 工具模拟有工具加载的情况
    import src.core.tools.integration_tools as mod
    original = list(mod.INTEGRATION_TOOLS)

    mock_tools = [
        MockTool("crm_list_customers"),    # read
        MockTool("crm_create_customer"),   # write
        MockTool("crm_get_customer"),      # read
        MockTool("crm_delete_customer"),   # write
        MockTool("ticket_create"),         # write (未来服务)
        MockTool("ticket_list"),           # read (未来服务)
    ]
    mod.INTEGRATION_TOOLS.clear()
    mod.INTEGRATION_TOOLS.extend(mock_tools)

    try:
        rules = get_integration_hitl_rules()
        assert len(rules) == 3, f"应有 3 个写操作规则，实际 {len(rules)}: {rules}"
        assert "crm_create_customer" in rules
        assert "crm_delete_customer" in rules
        assert "ticket_create" in rules
        assert "crm_list_customers" not in rules
        assert "crm_get_customer" not in rules
        assert "ticket_list" not in rules

        # 验证规则格式
        for tool_name, rule in rules.items():
            assert rule == {"allowed_decisions": ["approve", "reject"]}, f"{tool_name} 规则格式错误: {rule}"

        print(f"[OK] mock 6 个工具 → 3 个写操作自动生成 HITL 规则: {list(rules.keys())}")
    finally:
        # 恢复原始状态
        mod.INTEGRATION_TOOLS.clear()
        mod.INTEGRATION_TOOLS.extend(original)


# ---------------------------------------------------------------------------
# 测试 4: 三个 skill 都注入了 INTEGRATION_TOOLS
# ---------------------------------------------------------------------------
def test_skills_have_integration_tools():
    from src.core.tools import INTEGRATION_TOOLS
    from src.skills import SKILL_REGISTRY

    # 验证没有 crm skill
    assert "crm" not in SKILL_REGISTRY, "不应有独立的 crm skill"
    print("[OK] SKILL_REGISTRY 中无 crm skill（工具注入模式正确）")

    # 验证三个 skill 都存在
    assert set(SKILL_REGISTRY.keys()) == {"coding", "qa", "research"}
    print(f"[OK] 三个 skill 注册: {list(SKILL_REGISTRY.keys())}")

    # 验证每个 skill 的 tools 列表包含 INTEGRATION_TOOLS 的工具
    # （当 MCP server 未启动时 INTEGRATION_TOOLS 为空，所以只验证结构正确）
    for skill_id, skill in SKILL_REGISTRY.items():
        tools = skill.tools
        assert isinstance(tools, list), f"{skill_id}.tools 不是 list"
        # 验证 INTEGRATION_TOOLS 的内容在 skill tools 里
        for mcp_tool in INTEGRATION_TOOLS:
            assert mcp_tool in tools, f"{skill_id} 缺少 MCP 工具 {mcp_tool}"
        print(f"  {skill_id}: {len(tools)} 个工具（含 {len(INTEGRATION_TOOLS)} 个 MCP 工具）")

    print("[OK] 所有 skill 都注入了 INTEGRATION_TOOLS")


# ---------------------------------------------------------------------------
# 测试 5: skill 的 hitl_rules 包含 MCP 写操作规则
# ---------------------------------------------------------------------------
def test_skills_have_mcp_hitl_rules():
    from src.core.tools import get_integration_hitl_rules
    from src.skills import SKILL_REGISTRY

    mcp_rules = get_integration_hitl_rules()

    for skill_id, skill in SKILL_REGISTRY.items():
        rules = skill.hitl_rules
        assert isinstance(rules, dict)

        # coding skill 有自己的 HITL 规则 + MCP 规则
        if skill_id == "coding":
            assert "write_file" in rules, "coding skill 应保留原有 write_file 规则"
            assert "edit_file" in rules, "coding skill 应保留原有 edit_file 规则"
            assert "delete_file" in rules, "coding skill 应保留原有 delete_file 规则"

        # 所有 skill 的 MCP 规则都应包含在内
        for mcp_tool_name, mcp_rule in mcp_rules.items():
            assert mcp_tool_name in rules, f"{skill_id} 缺少 MCP 工具 {mcp_tool_name} 的 HITL 规则"

        print(f"  {skill_id}: {len(rules)} 条 HITL 规则")

    print("[OK] 所有 skill 的 hitl_rules 包含 MCP 写操作规则")


# ---------------------------------------------------------------------------
# 测试 6: reload() 机制
# ---------------------------------------------------------------------------
def test_reload_mechanism():
    from src.core.tools.integration_tools import INTEGRATION_TOOLS, reload

    # 记录原始 list 的 id（reload 应保持引用不变）
    original_id = id(INTEGRATION_TOOLS)

    # 调用 reload
    result = reload()

    # 验证返回的是同一个 list 对象（原地替换）
    assert id(INTEGRATION_TOOLS) == original_id, "reload 后 INTEGRATION_TOOLS 引用应不变"
    assert result is INTEGRATION_TOOLS, "reload() 应返回 INTEGRATION_TOOLS 本身"

    print(f"[OK] reload() 保持 list 引用不变 (id={original_id})")
    print(f"     reload 后工具数: {len(INTEGRATION_TOOLS)}")


# ---------------------------------------------------------------------------
# 测试 7: /admin/skills/reload 路由注册
# ---------------------------------------------------------------------------
def test_reload_endpoint_registered():
    from src.core.server import app

    routes = {r.path: r for r in app.routes if hasattr(r, "path")}
    assert "/admin/skills/reload" in routes, "缺少 /admin/skills/reload 路由"
    reload_route = routes["/admin/skills/reload"]
    assert "POST" in reload_route.methods, "路由应为 POST 方法"
    print("[OK] POST /admin/skills/reload 路由已注册")


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------
def main() -> int:
    tests = [
        ("配置解析 _parse_servers", test_parse_servers),
        ("写操作识别 _is_write_tool", test_is_write_tool),
        ("HITL 规则生成 get_integration_hitl_rules", test_get_integration_hitl_rules),
        ("skill 注入 INTEGRATION_TOOLS", test_skills_have_integration_tools),
        ("skill 包含 MCP HITL 规则", test_skills_have_mcp_hitl_rules),
        ("热重载机制 reload()", test_reload_mechanism),
        ("热重载端点注册", test_reload_endpoint_registered),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        print(f"\n{'='*60}")
        print(f"测试: {name}")
        print(f"{'='*60}")
        try:
            test_fn()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"[FAIL] {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*60}")
    print(f"结果: {passed} passed, {failed} failed, {len(tests)} total")
    print(f"{'='*60}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
