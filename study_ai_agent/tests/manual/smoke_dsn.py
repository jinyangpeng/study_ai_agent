"""直接测 DSN 能否在 psycopg async 下连接，绕开池子。"""
import asyncio
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

# 1) 最小 DSN
dsn_min = f"postgresql://{USER}:{PWD}@{HOST}:{PORT}/{DB}"
# 2) + hostaddr
dsn_hostaddr = f"{dsn_min}?hostaddr=127.0.0.1"
# 3) + search_path
dsn_schema = f"{dsn_hostaddr}&options=-c%20search_path%3D%22langgraph_checkpoints%22%2Cpublic"
# 4) + keepalives
dsn_full = f"{dsn_schema}&keepalives=1&keepalives_idle=60&keepalives_interval=10&keepalives_count=5"

print("=" * 60)
for label, dsn in [
    ("minimal", dsn_min),
    ("+hostaddr", dsn_hostaddr),
    ("+search_path", dsn_schema),
    ("+keepalives (full)", dsn_full),
]:
    print(f"\n=== {label} ===")
    print(f"  dsn: {dsn[:80]}{'...' if len(dsn) > 80 else ''}")
    try:
        async def go():
            conn = await asyncio.wait_for(
                psycopg.AsyncConnection.connect(dsn, autocommit=True),
                timeout=5.0,
            )
            try:
                await asyncio.wait_for(conn.execute("SELECT 1"), timeout=5.0)
            finally:
                await conn.close()
            return "ok"
        result = asyncio.run(go())
        print(f"  [OK] connect + SELECT 1 in <5s")
    except asyncio.TimeoutError:
        print(f"  [FAIL] timed out at 5s")
    except Exception as e:
        print(f"  [FAIL] {type(e).__name__}: {e}")
