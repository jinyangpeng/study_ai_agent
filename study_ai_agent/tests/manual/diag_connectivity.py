"""LLM 上游连通性最小化诊断脚本。

跑这个可以快速判断问题在「网络」还是在「应用」：

  1. 纯 TCP/HTTP 层能不能连到各家 LLM API
  2. 应用层 provider 能不能拿到 key 并发出请求（即使收不到响应也无所谓）
  3. 真实 chat 调用能跑通哪几家

跑法：
  .\\venv\\Scripts\\python.exe tests\\manual\\diag_connectivity.py
"""
import asyncio
import os
import socket
import time
import sys

from dotenv import load_dotenv
load_dotenv(".env")


def tcp_ping(host: str, port: int = 443, timeout: float = 5.0) -> tuple[bool, str]:
    """纯 TCP 握手，验证机器到目标 IP:port 通不通。"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, f"TCP {host}:{port} reachable in <{timeout}s"
    except OSError as e:
        return False, f"TCP {host}:{port} failed: {type(e).__name__}: {e}"


def http_ping(url: str, timeout: float = 8.0) -> tuple[bool, str]:
    """HTTP HEAD 看 endpoint 是不是有响应（不要求 200，404/401/403 都算通的）。"""
    try:
        import httpx
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            r = client.request("GET", url)
            return True, f"HTTP {r.status_code} ({len(r.content)}B)"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:150]}"


def show_env():
    print("\n[ENV] .env 关键变量")
    keys = ["QIANFAN_API_KEY", "ZAI_API_KEY", "DEEPSEEK_API_KEY", "DASHSCOPE_API_KEY"]
    for k in keys:
        v = os.environ.get(k, "")
        if v:
            print(f"  {k:24s} = {v[:20]}...{v[-8:]} (len={len(v)})")
        else:
            print(f"  {k:24s} = <EMPTY>")
    print(f"  HTTP_PROXY env        = {os.environ.get('HTTP_PROXY') or '<not set>'}")
    print(f"  HTTPS_PROXY env       = {os.environ.get('HTTPS_PROXY') or '<not set>'}")


def main():
    print("=" * 60)
    print("LLM 上游连通性诊断")
    print("=" * 60)
    show_env()

    targets = [
        ("DeepSeek",  "api.deepseek.com",       443, "https://api.deepseek.com/v1/models"),
        ("Zhipu",     "open.bigmodel.cn",       443, "https://open.bigmodel.cn/api/paas/v4/"),
        ("Qianfan",   "qianfan.baidubce.com",   443, "https://qianfan.baidubce.com/v2/"),
        ("OpenAI",    "api.openai.com",         443, "https://api.openai.com/v1/"),
        ("DashScope", "dashscope.aliyuncs.com", 443, "https://dashscope.aliyuncs.com/api/v1/"),
    ]

    print("\n[1/2] TCP 握手测试（网络层是否通）")
    for name, host, port, _ in targets:
        ok, msg = tcp_ping(host, port)
        marker = "[OK]" if ok else "[FAIL]"
        print(f"  {marker:7s} {name:10s} {msg}")

    print("\n[2/2] HTTP 端点测试（应用层 endpoint 是否响应）")
    for name, host, port, url in targets:
        ok, msg = http_ping(url)
        marker = "[OK]" if ok else "[FAIL]"
        print(f"  {marker:7s} {name:10s} GET {url}")
        print(f"               -> {msg}")

    print("\n" + "=" * 60)
    print("结论：")
    print("  * TCP 列全 [FAIL]  -> 网络层断了（防火墙 / VPN / 代理问题）")
    print("  * TCP OK HTTP FAIL -> TLS 握手被拦了（需要装证书 / 走代理）")
    print("  * 全 OK 但 LLM 仍 500 -> 是 API key 业务问题（欠费/失效）")
    print("  * HTTP 401/403/404 -> TCP+TLS 通了，业务侧拒绝（key 失效）")
    print("=" * 60)


if __name__ == "__main__":
    main()
