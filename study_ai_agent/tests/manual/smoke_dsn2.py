"""对比 DSN 启不启 keepalives，能不能用 SelectorEventLoop 正常跑。"""
import asyncio
import selectors
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import psycopg

USER = "postgres"
PWD = "123456"
HOST = "localhost"
PORT = 5432
DB = "postgres"

# 原始（我加 keepalives 之前的）DSN
dsn_old = (
    f"postgresql://{USER}:{PWD}@{HOST}:{PORT}/{DB}"
    "?hostaddr=127.0.0.1"
    "&options=-c%20search_path%3D%22langgraph_checkpoints%22%2Cpublic"
)
# 当前（带 keepalives）的 DSN
dsn_new = dsn_old + "&keepalives=1&keepalives_idle=60&keepalives_interval=10&keepalives_count=5"


async def go(label, dsn):
    print(f"\n=== {label} ===")
    print(f"  dsn: {dsn[:80]}{'...' if len(dsn) > 80 else ''}")
    print(f"  loop: {asyncio.get_running_loop().__class__.__name__}")
    try:
        # 用 5s 超时，免得 ProactorEventLoop 的卡死把整个测试拖死
        conn = await asyncio.wait_for(
            psycopg.AsyncConnection.connect(dsn, autocommit=True),
            timeout=5.0,
        )
        try:
            await asyncio.wait_for(conn.execute("SELECT 1"), timeout=5.0)
        finally:
            await conn.close()
        print(f"  [OK] connect + SELECT 1 in <5s")
        return True
    except asyncio.TimeoutError:
        print(f"  [FAIL] timed out at 5s (likely ProactorEventLoop or DSN issue)")
        return False
    except Exception as e:
        print(f"  [FAIL] {type(e).__name__}: {str(e)[:200]}")
        return False


async def main():
    print(f"outer loop = {type(asyncio.get_running_loop()).__name__}")

    ok_old = await go("OLD DSN (no keepalives)", dsn_old)
    ok_new = await go("NEW DSN (with keepalives)", dsn_new)

    print()
    print("=" * 60)
    if ok_old and ok_new:
        print("[OK] 两种 DSN 都能连，keepalives 不是问题")
    elif ok_old and not ok_new:
        print("[CONCLUSION] keepalives 是问题")
    elif not ok_old and not ok_new:
        print("[CONCLUSION] 都不是 DSN 问题，是别的地方")
    else:
        print("[UNEXPECTED]")


# Python 3.14 必需：显式传 loop_factory 强制 SelectorEventLoop。
# 在 3.14 上 set_event_loop_policy / set_event_loop 都被忽视，
# asyncio.run() 默认会建 ProactorEventLoop。
asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
