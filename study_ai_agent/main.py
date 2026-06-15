"""Main entry.

``python main.py`` 直接拉起 uvicorn。Windows 上需要在 run 之前
注入 :class:`asyncio.SelectorEventLoop`（psycopg3 async 兼容），
否则 uvicorn 默认的 ProactorEventLoop 会让 lifespan 里的连接池
启动直接挂掉。Linux / macOS 走 :func:`asyncio.DefaultEventLoop`。
"""
import asyncio
import selectors
import sys

import uvicorn

from src.core.server import app


def _make_event_loop() -> asyncio.AbstractEventLoop:
    if sys.platform == "win32":
        return asyncio.SelectorEventLoop(selectors.SelectSelector())
    return asyncio.DefaultEventLoop()


if __name__ == "__main__":
    from src.config.settings import settings

    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT,
        log_level=settings.LOG_LEVEL.lower(),
        # uvicorn 0.30+：``loop`` 可直接接收 loop factory
        loop=_make_event_loop,
    )
