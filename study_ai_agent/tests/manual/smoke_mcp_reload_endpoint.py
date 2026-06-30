# -*- coding: utf-8 -*-
"""热重载端点集成测试 —— 用 FastAPI TestClient 直接测，不需要启动完整 server。"""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["MCP_SERVERS"] = "crm=http://localhost:8001/mcp"
os.environ["CHECKPOINTER_BACKEND"] = "memory"

from fastapi.testclient import TestClient  # noqa: E402


def main() -> int:
    from src.core.server import app

    with TestClient(app) as client:
        # 1. POST /admin/skills/reload
        print("=== POST /admin/skills/reload ===")
        resp = client.post("/admin/skills/reload")
        print(f"Status: {resp.status_code}")
        data = resp.json()
        print(f"Reloaded: {data['reloaded']}")
        print(f"MCP tool count: {data['mcp_tool_count']}")
        print(f"Graph cache cleared: {data['graph_cache_cleared']}")
        names = data["mcp_tool_names"]
        print(f"Tool names (first 5): {names[:5]}")

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        assert data["reloaded"] is True
        assert data["mcp_tool_count"] == 28, f"Expected 28 tools, got {data['mcp_tool_count']}"
        assert data["graph_cache_cleared"] is True
        print("\n[OK] 热重载端点工作正常")

        # 2. GET /skeletons
        print("\n=== GET /skeletons ===")
        resp = client.get("/skeletons")
        skeletons = resp.json()
        skill_ids = [s["id"] for s in skeletons["skeletons"]]
        print(f"Skills: {skill_ids}")
        assert "crm" not in skill_ids, "不应有独立 crm skill"
        assert set(skill_ids) == {"coding", "qa", "research"}
        # 验证每个 skill 都有 CRM 工具（tool_count > 原始数量）
        for s in skeletons["skeletons"]:
            print(f"  {s['id']}: {s['tool_count']} tools")
        print("[OK] /skeletons 返回三个 skill（无独立 crm skill），且 tool_count 包含 CRM 工具")

        # 3. GET /health
        print("\n=== GET /health ===")
        resp = client.get("/health")
        print(f"Status: {resp.status_code}, Body: {resp.json()}")
        assert resp.status_code == 200
        print("[OK] /health 正常")

        # 4. 再次 reload 验证幂等性
        print("\n=== POST /admin/skills/reload (第二次) ===")
        resp = client.post("/admin/skills/reload")
        data = resp.json()
        assert resp.status_code == 200
        assert data["mcp_tool_count"] == 28
        print("[OK] 第二次 reload 仍返回 28 个工具（幂等）")

    print("\n[ALL OK] 所有端点测试通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
