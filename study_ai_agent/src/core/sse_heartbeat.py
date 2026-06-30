# -*- coding: utf-8 -*-
"""SSE 心跳辅助（#7）。

设计
----
长时间无事件的 SSE 流（LLM 思考中、工具执行中）容易被中间代理 /
防火墙 / 浏览器超时断开。定期发心跳（SSE 注释行 ``:keep-alive\\n\\n``）
能保活连接，且注释行不会被 EventSource 的 onmessage 看到，前端无感知。

实现
----
用 :class:`asyncio.Queue` 合并两个异步源：
1. 主事件流（agent 产生的事件）
2. 心跳定时器（每 ``interval`` 秒发一次 ``HEARTBEAT`` 哨兵）

主事件流结束 / 抛异常时，心跳自动停止。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)

#: 心跳哨兵对象（放进 queue 表示"该发心跳了"）
_HEARTBEAT_SENTINEL = object()

#: SSE 心跳行（SSE 注释，以 ``:`` 开头，EventSource 不触发 onmessage）
HEARTBEAT_LINE = b": keep-alive\n\n"


async def with_heartbeat(
    events: AsyncIterator[Any],
    interval: float,
) -> AsyncIterator[Any]:
    """给 ``events`` 流叠加心跳。

    每隔 ``interval`` 秒若主事件流没产出，就 yield 一个心跳哨兵。
    主事件流结束 / 抛异常时，心跳协程自动取消。

    :param events: 主事件流（agent 产生的事件）
    :param interval: 心跳间隔（秒）。``<=0`` 时关闭心跳，直接透传 ``events``
    :yields: 主事件流的事件，或 ``HEARTBEAT_SENTINEL``（调用方应发 ``HEARTBEAT_LINE``）
    """
    if interval <= 0:
        # 心跳关闭 → 直接透传
        async for event in events:
            yield event
        return

    queue: asyncio.Queue = asyncio.Queue(maxsize=64)

    async def _pump_events():
        """从主事件流拉事件放进 queue。"""
        try:
            async for event in events:
                await queue.put(event)
        except (asyncio.CancelledError, GeneratorExit):
            raise
        except Exception as exc:
            # 把异常传给合并协程，让它重新抛出
            await queue.put(exc)
        finally:
            # 主事件流结束 → 放 None 哨兵
            await queue.put(None)

    async def _pump_heartbeat():
        """定时放心跳哨兵。"""
        try:
            while True:
                await asyncio.sleep(interval)
                await queue.put(_HEARTBEAT_SENTINEL)
        except (asyncio.CancelledError, GeneratorExit):
            # 主事件流结束 → 心跳协程被取消，正常退出
            pass

    pump_task = asyncio.create_task(_pump_events())
    heartbeat_task = asyncio.create_task(_pump_heartbeat())

    try:
        while True:
            item = await queue.get()
            if item is None:
                # 主事件流正常结束
                break
            if item is _HEARTBEAT_SENTINEL:
                yield item
                continue
            if isinstance(item, Exception):
                # 主事件流抛异常 → 重新抛出
                raise item
            yield item
    finally:
        # 确保两个 pump task 都被取消（防止泄漏）
        for task in (pump_task, heartbeat_task):
            if not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass


def is_heartbeat(item: Any) -> bool:
    """判断 ``item`` 是否是心跳哨兵。"""
    return item is _HEARTBEAT_SENTINEL


__all__ = [
    "HEARTBEAT_LINE",
    "is_heartbeat",
    "with_heartbeat",
]
