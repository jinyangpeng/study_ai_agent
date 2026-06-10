"""直接测试各 provider 的连通性"""
import asyncio
import os

import httpx
from dotenv import load_dotenv

load_dotenv(".env")


async def test_qianfan():
    key = os.environ.get("QIANFAN_API_KEY", "")
    if not key:
        print("QIANFAN: no key")
        return
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                "https://qianfan.baidubce.com/v2/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": "ernie-3.5-8k",
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": False,
                },
            )
            print(f"QIANFAN: status={r.status_code} body={r.text[:200]}")
    except Exception as e:
        print(f"QIANFAN: {type(e).__name__}: {str(e)[:200]}")


async def test_zhipuai():
    key = os.environ.get("ZAI_API_KEY", "")
    if not key:
        print("ZHIPUAI: no key")
        return
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": "glm-4-flash",
                    "messages": [{"role": "user", "content": "hi"}],
                },
            )
            print(f"ZHIPUAI: status={r.status_code} body={r.text[:200]}")
    except Exception as e:
        print(f"ZHIPUAI: {type(e).__name__}: {str(e)[:200]}")


async def test_deepseek():
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        print("DEEPSEEK: no key")
        return
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                "https://api.deepseek.com/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": "hi"}],
                },
            )
            print(f"DEEPSEEK: status={r.status_code} body={r.text[:200]}")
    except Exception as e:
        print(f"DEEPSEEK: {type(e).__name__}: {str(e)[:200]}")


async def main():
    await test_qianfan()
    await test_zhipuai()
    await test_deepseek()


if __name__ == "__main__":
    asyncio.run(main())
