"""AG-UI 端点测试脚本 - 模拟 .http 文件中的 case 3-5。

AG-UI 端点 (POST /) 返回的是 SSE (Server-Sent Events)，
VSCode REST Client 处理 SSE 体验差，所以用 Python 来测。
"""
import asyncio
import json

import httpx


async def test_agui(skill: str | None, message: str, thread_id: str, label: str) -> None:
    """发送 AG-UI 请求并打印解析后的事件流。"""
    forwarded = {"skill": skill} if skill else {}
    payload = {
        "thread_id": thread_id,
        "run_id": f"run-{thread_id}",
        "messages": [
            {"role": "user", "id": f"msg-{thread_id}", "content": message}
        ],
        "tools": [],
        "context": [],
        "forwarded_props": forwarded,
        "state": {},
    }
    print(f"\n===== {label} =====")
    print(f"POST /  forwarded_props={forwarded}")
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream("POST", "http://127.0.0.1:8000/", json=payload) as resp:
                print(f"HTTP {resp.status_code}  Content-Type={resp.headers.get('content-type')}")
                if resp.status_code != 200:
                    body = await resp.aread()
                    print(f"body: {body[:300]!r}")
                    return
                count = 0
                saw_done = False
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("data:"):
                        data = line[5:].strip()
                        if not data or data == "[DONE]":
                            if data == "[DONE]":
                                saw_done = True
                            continue
                        try:
                            ev = json.loads(data)
                        except json.JSONDecodeError:
                            print(f"  [raw] {line[:200]}")
                            continue
                        count += 1
                        ev_type = ev.get("type", "?")
                        ev_name = ev.get("name", "")
                        snippet = ""
                        if ev_type == "TEXT_MESSAGE_CONTENT":
                            snippet = repr(ev.get("delta", ""))[:60]
                        elif ev_type == "TOOL_CALL_START":
                            snippet = f"name={ev.get('toolCallName', '')}"
                        elif ev_type == "STATE_SNAPSHOT":
                            snapshot = ev.get("snapshot", {})
                            keys = list(snapshot.keys())
                            snippet = f"keys={keys}"
                        print(f"  [{count:02d}] {ev_type:30s} {ev_name:20s} {snippet}")
                print(f"  total events: {count}  saw [DONE]: {saw_done}")
    except httpx.HTTPStatusError as e:
        print(f"  HTTP error: {e}")
    except Exception as e:
        print(f"  Error: {type(e).__name__}: {e}")


async def main():
    await test_agui(
        skill="coding",
        message="用一句话解释 make_execute_node 的作用",
        thread_id="agui-coding-1",
        label="AG-UI 编程骨架",
    )
    await test_agui(
        skill="research",
        message="总结 2025 年 LLM agent 框架的主要趋势，并给出至少 3 个引用来源",
        thread_id="agui-research-1",
        label="AG-UI 深度研究骨架",
    )
    await test_agui(
        skill=None,
        message="你好，介绍一下你自己",
        thread_id="agui-default-1",
        label="AG-UI 省略 skill（默认 = research）",
    )
    await test_agui(
        skill="nonexistent_skill",
        message="随便聊点什么",
        thread_id="agui-error-1",
        label="AG-UI 未知 skill（应返回 400）",
    )


if __name__ == "__main__":
    asyncio.run(main())
