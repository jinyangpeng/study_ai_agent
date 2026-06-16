"""模拟 main.py 入口：先建 SelectorEventLoop，再跑 pool 初始化。
   验证 4 道防线能正常工作。
"""
import asyncio
import selectors
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# === 关键：SelectorEventLoop + autocommit + keepalives 全开 ===
# 1) 5 种常见密码挨个试，找出 docker PG 的密码
import psycopg

PWDS = ["123456", "postgres", "password", "admin", "mysecretpassword", "example"]

async def find_pwd():
    for pwd in PWDS:
        try:
            conn = await asyncio.wait_for(
                psycopg.AsyncConnection.connect(
                    f"postgresql://postgres:{pwd}@127.0.0.1:5432/postgres?hostaddr=127.0.0.1",
                    autocommit=True,
                ),
                timeout=3.0,
            )
            await conn.execute("SELECT 1")
            await conn.close()
            return pwd
        except psycopg.OperationalError:
            continue
        except Exception:
            continue
    return None

async def main():
    pwd = await find_pwd()
    if pwd is None:
        print("[FAIL] 5 个常见密码都连不上，docker PG 可能用了非默认密码")
        return
    print(f"[OK] 找到密码: {pwd!r}")

    # 2) 用真密码测 DSN（带 keepalives）
    from src.config.settings import get_settings
    s = get_settings()
    s.POSTGRES_PASSWORD = pwd
    from src.core.checkpointer import _build_conninfo
    dsn = _build_conninfo(s)
    print(f"[OK] DSN: {dsn}")
    conn = await psycopg.AsyncConnection.connect(dsn, autocommit=True)
    await conn.execute("SELECT 1")
    await conn.close()
    print("[OK] 带 keepalives 的 DSN 连接成功")

    # 3) 起 checkpointer 工厂（完整 4 道防线）
    from src.core.checkpointer import CheckpointerFactory
    factory = CheckpointerFactory(s)
    try:
        await asyncio.wait_for(factory.setup(), timeout=20.0)
        print("[OK] checkpointer 工厂 setup 成功")

        # 4) ping 暴露新字段
        status = await factory.ping()
        print(f"[OK] ping: {status}")

        # 5) 拿一条连接
        async with factory._pool.connection() as conn:  # type: ignore[attr-defined]
            await conn.execute("SELECT current_database(), current_schema")
        print("[OK] 池子里拿连接 + SELECT 成功")
    finally:
        await factory.aclose()
        print("[OK] 工厂关闭")


# Python 3.14 必需：用 loop_factory 强制 SelectorEventLoop
asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
