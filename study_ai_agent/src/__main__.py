"""本地开发启动入口（``python -m src`` / ``python src/__main__.py``）。

解决 Windows + Python 3.14 + uvicorn 的事件循环兼容问题：
psycopg3 async **必须**跑在 :class:`asyncio.SelectorEventLoop` 上；
但 uvicorn 默认走 :class:`asyncio.ProactorEventLoop`（Windows），

我们用 uvicorn 的 ``loop_factory`` 参数在 run 之前注入正确的
事件循环工厂 —— 这是 uvicorn >=0.30 的官方推荐做法，比
``set_event_loop_policy()`` 更稳（后者即将在 Python 3.16 移除）。
"""

# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import selectors
import sys


def _make_event_loop() -> asyncio.AbstractEventLoop:
    """根据平台返回合适的事件循环。

    * Windows：``SelectorEventLoop``（psycopg3 async 兼容）。
    * 其它：``DefaultEventLoop``（Linux 上通常就是 ``SelectorEventLoop``），
      让 uvicorn 自己挑。
    """
    if sys.platform == "win32":
        return asyncio.SelectorEventLoop(selectors.SelectSelector())
    return asyncio.DefaultEventLoop()


if __name__ == "__main__":
    import uvicorn

    from src.config.settings import settings

    uvicorn.run(
        "src.core.server:app",
        host=settings.HOST,
        port=settings.PORT,
        log_level=settings.LOG_LEVEL.lower(),
        # uvicorn 0.30+ 支持把 ``loop`` 直接传成「返回 AbstractEventLoop 的可调用对象」
        # 当作 loop factory 用 —— 这里 Windows 注入 SelectorEventLoop，
        # 其它平台走 default。
        loop=_make_event_loop,
    )
