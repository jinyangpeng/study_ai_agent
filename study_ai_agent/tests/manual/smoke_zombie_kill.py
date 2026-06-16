"""端到端验证 4 道防线：杀掉池子里一个连接，看 check 钩子能否自动重建。"""
import asyncio
import json
import sys
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import psycopg  # noqa: E402

ADMIN_DSN = (
    "postgresql://postgres:123456@127.0.0.1:5432/postgres"
    "?hostaddr=127.0.0.1"
)


def health() -> dict:
    return json.loads(urllib.request.urlopen("http://localhost:8000/health").read())


def list_pool_pids() -> list[tuple]:
    """列出当前数据库所有非 self 连接的 pid。
       池子连接用 application_name='psycopg' 标识，但保险起见不过滤。
    """
    my_pid = psycopg.connect(ADMIN_DSN, autocommit=True).info.backend_pid
    conn = psycopg.connect(ADMIN_DSN, autocommit=True)
    rows = conn.execute(
        """
        SELECT pid, state, application_name
        FROM pg_stat_activity
        WHERE datname = current_database()
          AND pid != pg_backend_pid()
        ORDER BY pid
        """
    ).fetchall()
    conn.close()
    return rows


def kill_pid(pid: int) -> None:
    killer = psycopg.connect(ADMIN_DSN, autocommit=True)
    killer.execute(f"SELECT pg_terminate_backend({pid})")
    killer.close()


def show(label, h):
    p = h["checkpointer"]["pool"]
    print(
        f"  {label}: ok={h['checkpointer']['ok']} "
        f"size={p['size']} avail={p['available']} "
        f"requests={p['requests_num']} usage_ms={p['usage_ms']}"
    )


async def main():
    print("=== Step 0: 初始状态 ===")
    show("baseline", health())

    print()
    print("=== Step 1: 找池子里所有连接 ===")
    pids = list_pool_pids()
    target = pids[0][0]
    print(f"  target pid: {target}")

    print()
    print(f"=== Step 2: pg_terminate_backend({target}) ===")
    kill_pid(target)
    print("  [OK] 杀掉了")

    print()
    print("=== Step 3: /health 触发 getconn 走 check 钩子 ===")
    show("after kill", health())

    print()
    print("=== Step 4: 验证 check 钩子能扛住 ===")
    if health()["checkpointer"]["ok"]:
        print("  [OK] check 钩子自动重建坏连接")
    else:
        print("  [FAIL] 服务挂了")

    print()
    print("=== Step 5: 连续 5 次 getconn 压测 ===")
    for i in range(5):
        show(f"iter {i+1}", health())


asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
