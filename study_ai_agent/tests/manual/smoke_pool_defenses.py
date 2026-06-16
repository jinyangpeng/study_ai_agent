"""逐步诊断：先单独测 DSN + keepalives，再加 check / max_idle / max_lifetime。"""
import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 强制走 development env
os.environ["ENV"] = "development"

from src.config.settings import get_settings  # noqa: E402
from src.core.checkpointer import (  # noqa: E402
    _build_conninfo,
    _check_connection_health,
)
from psycopg_pool import AsyncConnectionPool  # noqa: E402

s = get_settings()
print("=== Settings ===")
print(f"  HOST={s.POSTGRES_HOST} PORT={s.POSTGRES_PORT}")
print(f"  POOL min={s.POSTGRES_POOL_MIN_SIZE} max={s.POSTGRES_POOL_MAX_SIZE}")
print(f"  POOL check={s.POSTGRES_POOL_CHECK} max_idle={s.POSTGRES_POOL_MAX_IDLE} max_lifetime={s.POSTGRES_POOL_MAX_LIFETIME}")
print(f"  keepalives={s.POSTGRES_KEEPALIVES} idle={s.POSTGRES_KEEPALIVES_IDLE} interval={s.POSTGRES_KEEPALIVES_INTERVAL} count={s.POSTGRES_KEEPALIVES_COUNT}")

dsn = _build_conninfo(s)
print()
print("=== DSN ===")
print(f"  {dsn}")

# Step 1: 最小池子，不带 check / max_idle / max_lifetime，只测 DSN 通不通
print()
print("=== Step 1: minimal pool, no extras ===")
async def test_minimal():
    pool = AsyncConnectionPool(
        conninfo=dsn,
        min_size=2,
        max_size=4,
        timeout=10.0,
        kwargs={"autocommit": True},
        open=False,
    )
    await pool.open(wait=True, timeout=10.0)
    print("  [OK] pool opened with min_size=2")
    async with pool.connection() as conn:
        await conn.execute("SELECT 1")
    print("  [OK] SELECT 1 works")
    print(f"  stats: {pool.get_stats()}")
    await pool.close()
    print("  [OK] pool closed")

asyncio.run(test_minimal())

# Step 2: 加 check
print()
print("=== Step 2: pool with check=SELECT 1 ===")
async def test_with_check():
    pool = AsyncConnectionPool(
        conninfo=dsn,
        min_size=2,
        max_size=4,
        timeout=10.0,
        kwargs={"autocommit": True},
        check=_check_connection_health,
        open=False,
    )
    await pool.open(wait=True, timeout=10.0)
    print("  [OK] pool opened with check")
    async with pool.connection() as conn:
        await conn.execute("SELECT 1")
    print("  [OK] SELECT 1 works (check ran during getconn)")
    print(f"  stats: {pool.get_stats()}")
    await pool.close()
    print("  [OK] pool closed")

asyncio.run(test_with_check())

# Step 3: 全部加
print()
print("=== Step 3: full pool (check + max_idle + max_lifetime) ===")
async def test_full():
    pool = AsyncConnectionPool(
        conninfo=dsn,
        min_size=2,
        max_size=4,
        timeout=10.0,
        kwargs={"autocommit": True},
        check=_check_connection_health,
        max_idle=s.POSTGRES_POOL_MAX_IDLE,
        max_lifetime=s.POSTGRES_POOL_MAX_LIFETIME,
        open=False,
    )
    await pool.open(wait=True, timeout=10.0)
    print("  [OK] full pool opened")
    async with pool.connection() as conn:
        await conn.execute("SELECT 1")
    print("  [OK] SELECT 1 works")
    print(f"  stats: {pool.get_stats()}")
    await pool.close()
    print("  [OK] pool closed")

asyncio.run(test_full())
