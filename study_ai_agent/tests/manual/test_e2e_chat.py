"""前后端对话功能冒烟测试（v2：抓全量网络 + 错误 toast）。"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r"c:\Workspace\Development\Study\study_ai_agent\debug-executor-node-panic")
OUT.mkdir(parents=True, exist_ok=True)

console_logs: list[dict] = []
network_log: list[dict] = []
network_failures: list[dict] = []
page_errors: list[str] = []


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        page.on("console", lambda msg: console_logs.append({
            "type": msg.type,
            "text": msg.text,
        }))
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        def on_request_finished(req):
            try:
                resp = req.response()
                network_log.append({
                    "method": req.method,
                    "url": req.url,
                    "status": resp.status if resp else None,
                    "ct": resp.headers.get("content-type") if resp else None,
                })
            except Exception:
                network_log.append({"method": req.method, "url": req.url, "status": "?"})

        page.on("requestfinished", on_request_finished)
        page.on("requestfailed", lambda req: network_failures.append({
            "url": req.url,
            "failure": req.failure,
            "method": req.method,
        }))

        print(">>> navigate http://localhost:3000")
        page.goto("http://localhost:3000", timeout=30_000, wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle", timeout=15_000)
        # 等 skeletons 二次请求到位（StrictMode 会跑两次 effect）
        time.sleep(2)
        print(">>> page loaded, taking initial screenshot")
        page.screenshot(path=str(OUT / "01-home.png"), full_page=True)

        # 打印一下网络请求概况
        print(f">>> network log so far ({len(network_log)} reqs):")
        for r in network_log:
            print(f"    {r['method']} {r['url']} -> {r.get('status')} ct={r.get('ct')}")
        print(f">>> network failures: {len(network_failures)}")
        for r in network_failures:
            print(f"    FAIL {r['method']} {r['url']} :: {r['failure']}")

        # 找 composer
        composer = page.locator("textarea").first
        if composer.count() == 0:
            print("!!! composer (textarea) not found")
            page.screenshot(path=str(OUT / "no-composer.png"), full_page=True)
            browser.close()
            return 2

        test_q = "你好，请用一句话介绍你自己。"
        print(f">>> typing: {test_q}")
        composer.fill(test_q)
        page.screenshot(path=str(OUT / "02-typed.png"), full_page=True)

        # 找发送按钮（取最后一个可见的 svg button）
        send = None
        for sel in [
            "form button[type='submit']",
            "button[aria-label*='发']",
            "button:has-text('发送')",
        ]:
            loc = page.locator(sel).last
            if loc.count() > 0 and loc.is_visible() and loc.is_enabled():
                send = loc
                break
        if send is None:
            print(">>> no send button, try Enter key")
            composer.press("Enter")
        else:
            print(f">>> clicking send")
            send.click()

        # 等 assistant 文本或者错误 toast
        print(">>> waiting for response (max 90s)")
        deadline = time.time() + 90
        last_assistant_text = ""
        error_toast_text = ""
        last_network_count = len(network_log)
        seen_post = False
        while time.time() < deadline:
            # 收集所有 assistant 消息
            try:
                bubbles = page.locator("[data-message-role='assistant']").all()
                for b in bubbles:
                    t = b.inner_text().strip()
                    if t and len(t) > len(last_assistant_text):
                        last_assistant_text = t
            except Exception:
                pass

            # 收集错误 toast
            try:
                toasts = page.locator("[data-testid='chat-error-toast']").all()
                for t_ in toasts:
                    txt = t_.inner_text().strip()
                    if txt:
                        error_toast_text = txt
            except Exception:
                pass

            # 检查新请求
            if len(network_log) > last_network_count:
                for r in network_log[last_network_count:]:
                    if r.get("method") == "POST" and r.get("url", "").endswith("/"):
                        seen_post = True
                        print(f">>> saw POST: {r['url']} -> {r.get('status')}")
                last_network_count = len(network_log)

            # 终局条件
            if error_toast_text:
                print(">>> error toast appeared")
                break
            if seen_post and any(
                r.get("method") == "POST"
                and r.get("url", "").endswith("/")
                and r.get("status") in (500, 502, 503, 504)
                for r in network_log
            ):
                print(">>> POST returned 5xx")
                break
            if last_assistant_text and len(last_assistant_text) > 20:
                print(">>> got non-trivial assistant text")
                break
            time.sleep(2)

        page.screenshot(path=str(OUT / "03-after-send.png"), full_page=True)
        # 关键页面文字 dump（备用）
        try:
            (OUT / "page-text.html").write_text(page.content(), encoding="utf-8")
        except Exception as e:
            print(f"warn page.content: {e}")

        report = {
            "seen_post": seen_post,
            "last_assistant_text": last_assistant_text,
            "error_toast_text": error_toast_text,
            "page_errors": page_errors,
            "network_log": network_log,
            "network_failures": network_failures,
            "console_errors": [c for c in console_logs if c["type"] in ("error",)],
            "console_warnings": [c for c in console_logs if c["type"] in ("warning",)],
        }
        (OUT / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print("=" * 60)
        print(json.dumps({
            k: report[k] for k in [
                "seen_post", "last_assistant_text", "error_toast_text",
                "page_errors", "console_errors",
            ]
        }, ensure_ascii=False, indent=2))
        print("--- network summary ---")
        for r in network_log:
            print(f"  {r.get('method')} {r.get('url')} -> {r.get('status')}")
        print(f"--- failures ({len(network_failures)}) ---")
        for r in network_failures:
            print(f"  {r.get('method')} {r.get('url')} :: {r.get('failure')}")

        browser.close()
        return 0


if __name__ == "__main__":
    sys.exit(main())
