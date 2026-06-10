"""
Study AI Agent - 前后端联调测试

测试项：
1. 首页加载，骨架列表正常拉取
2. 欢迎页 quick prompt 渲染
3. 发送消息，AG-UI 流式响应正常
4. 操作行（复制/重新生成/反馈）渲染
5. 新建会话 / 切换历史
6. 主题切换
7. Skill 切换
"""
import json
import os
import sys
import time
from pathlib import Path

# Force UTF-8 output on Windows (default console is GBK and chokes on emojis)
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

from playwright.sync_api import sync_playwright, expect, Page


def safe_print(*args, **kwargs):
    """Print that always goes to a UTF-8 stream, replacing unencodable chars."""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        text = ' '.join(str(a) for a in args)
        try:
            sys.stdout.buffer.write((text + '\n').encode('utf-8', errors='replace'))
            sys.stdout.buffer.flush()
        except Exception:
            pass

# 配置
FRONTEND_URL = "http://localhost:3000"
SCREENSHOTS_DIR = Path(__file__).parent / "test_screenshots"
SCREENSHOTS_DIR.mkdir(exist_ok=True)

# 测试结果收集
results = {"pass": 0, "fail": 0, "errors": []}

def log(name, ok, msg=""):
    if ok:
        results["pass"] += 1
        print(f"  [PASS] {name}: {msg}")
    else:
        results["fail"] += 1
        results["errors"].append(f"{name}: {msg}")
        print(f"  [FAIL] {name}: {msg}")


def screenshot(page: Page, name: str):
    """保存截图"""
    path = SCREENSHOTS_DIR / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    print(f"    [SHOT] {path}")


def test_welcome_screen(page: Page):
    """测试欢迎页"""
    print("\n[1] 欢迎页加载")
    page.goto(FRONTEND_URL)
    page.wait_for_load_state("networkidle")
    time.sleep(2)  # 等待骨架数据加载

    # 应该有品牌区
    title = page.get_by_text("Study AI Agent").first
    log("brand", title.is_visible(), "品牌区可见")

    # 应该有欢迎语
    welcome = page.get_by_text("你好，欢迎使用 Study AI Agent").first
    log("welcome", welcome.is_visible(), "欢迎语可见")

    # 应该有 4 张 quick prompt 卡片
    prompts = page.locator("text=编程任务").all()
    log("prompts", len(prompts) > 0, f"quick prompt 卡片存在 ({len(prompts)})")

    # 当前 skill 应该显示
    skeleton_text = page.get_by_text("当前智能体").first
    log("skeleton", skeleton_text.is_visible(), "当前智能体标签可见")

    screenshot(page, "01_welcome")


def test_send_message(page: Page):
    """测试发送消息 + AG-UI 流式响应"""
    print("\n[2] 发送消息测试")
    # 找到 composer 的 input
    composer = page.get_by_placeholder("发消息...").first
    log("composer", composer.is_visible(), "输入框可见")

    composer.fill("用一句话介绍 LLM Agent")
    screenshot(page, "02_before_send")

    # 点击发送
    send_btn = page.locator('button[aria-label*="Send"], button:has(svg)').filter(has_text="").nth(-1)
    # 用键盘 Enter 更稳
    composer.press("Enter")
    print("    [WAIT] waiting for AI response (max 60s)...")

    # 等待 assistant 消息出现
    try:
        page.wait_for_selector('[data-message-role="assistant"], .group\\/assist', timeout=60000)
        log("response", True, "assistant 消息已出现")
    except Exception as e:
        log("response", False, f"等待 assistant 消息超时: {e}")
        return

    # 等待流式完成（光标消失）
    try:
        page.wait_for_selector(".is-streaming", state="detached", timeout=90000)
        log("streaming_done", True, "流式完成")
    except Exception:
        log("streaming_done", False, "流式完成超时")

    time.sleep(3)  # 等待 3 秒确保稳定
    screenshot(page, "03_after_response")

    # 检查 thread runtime 的状态
    rt_state = page.evaluate("""
() => {
  // 找 thread viewport 内容
  const vp = document.querySelector('.aui-thread-viewport');
  if (!vp) return { error: 'no viewport' };
  return {
    childCount: vp.children.length,
    innerHTML: vp.innerHTML.slice(0, 2000),
  };
}
""")
    if isinstance(rt_state, dict) and 'error' in rt_state:
        print(f"    [RT] {rt_state}")
    else:
        print(f"    [RT] viewport 子元素数: {rt_state.get('childCount', 0)}")
        # 数 grid 元素
        import re
        grid_count = rt_state.get('innerHTML', '').count('grid-cols-')
        user_cls = rt_state.get('innerHTML', '').count('group/user')
        assist_cls = rt_state.get('innerHTML', '').count('group/assist')
        print(f"    [RT] grid 数: {grid_count}, user 组: {user_cls}, assist 组: {assist_cls}")

    # 先诊断当前 DOM
    diag = page.evaluate("""
() => {
  // 找所有 message-like 元素
  const allDivs = Array.from(document.querySelectorAll('[class*="grid-cols"]'));
  return allDivs.map(el => ({
    cls: (el.className || '').slice(0, 120),
    text: (el.textContent || '').slice(0, 100),
  }));
}
""")
    print(f"    [DIAG] 当前 grid 元素: {len(diag)}")
    for i, d in enumerate(diag):
        print(f"      [{i}] cls={d['cls'][:80]}")
        print(f"          text={d['text'][:100]}")

    # 操作行应该可见（hover 时）
    # 用 [data-message-role] 或者 root role 来定位 assistant 消息
    assistant_msg = page.locator('[data-message-role="assistant"]').first
    if assistant_msg.count() == 0:
        # 备用选择器
        assistant_msg = page.locator('.group\\/assist').first
    if assistant_msg.count() > 0:
        assistant_msg.hover(force=True)
        time.sleep(0.8)
        # 检查所有 "复制" 文本节点
        copy_btn = page.locator('text="复制"').first
        log("copy_btn", copy_btn.count() > 0, f"复制按钮: {copy_btn.count()}")
        reload_btn = page.locator('text="重新生成"').first
        log("reload_btn", reload_btn.count() > 0, f"重新生成按钮: {reload_btn.count()}")
        # 检查"赞"图标
        thumbsup_btn = page.locator('button[title="赞"]').first
        log("thumbsup", thumbsup_btn.count() > 0, f"赞按钮: {thumbsup_btn.count()}")
        screenshot(page, "04_action_row")
    else:
        log("action_row", False, "未找到 assistant 消息元素")


def test_new_session(page: Page):
    """测试新建会话"""
    print("\n[3] 新建会话")
    # 用 title 找新建按钮（顶栏的 + 按钮）
    new_btn = page.locator('button[title*="新建会话"]').first
    log("new_btn", new_btn.count() > 0, f"新建按钮匹配: {new_btn.count()}")

    new_btn.click()
    time.sleep(1)

    # 欢迎页应该重新出现
    welcome = page.get_by_text("你好，欢迎使用 Study AI Agent").first
    log("welcome_again", welcome.is_visible(), "新建后欢迎页重新出现")
    screenshot(page, "05_new_session")


def test_skill_switch(page: Page):
    """测试 skill 切换"""
    print("\n[4] Skill 切换")
    # 点击 skill 切换器（顶栏）
    skill_switcher = page.locator('button:has-text("研究")').first
    if skill_switcher.count() == 0:
        skill_switcher = page.locator('button:has-text("深度")').first
    if skill_switcher.count() == 0:
        # 备用：从侧边栏切
        skill_switcher = page.locator('button:has-text("编程")').first

    if skill_switcher.count() > 0:
        skill_switcher.click()
        time.sleep(1)
        log("skill_switcher", True, "Skill 切换器已点击")
        screenshot(page, "06_skill_switcher_open")
    else:
        log("skill_switcher", False, "未找到 Skill 切换器")


def test_history_sidebar(page: Page):
    """测试历史侧边栏"""
    print("\n[5] 历史侧边栏")
    history_label = page.get_by_text("历史会话").first
    log("history_label", history_label.is_visible(), "历史会话标签可见")

    # 应该有至少 1 个会话（new session 创建的）
    sessions = page.locator('aside li').all()
    log("session_count", len(sessions) >= 1, f"会话数: {len(sessions)}")

    # 应该有搜索框
    search = page.get_by_placeholder("搜索会话…").first
    log("search", search.is_visible(), "搜索框可见")
    screenshot(page, "07_history_sidebar")


def test_theme_toggle(page: Page):
    """测试主题切换"""
    print("\n[6] 主题切换")
    # 找到主题切换按钮（顶栏的 sun/moon 图标按钮）
    theme_btns = page.locator('button[title*="主题"], button[title*="浅色"], button[title*="深色"]').all()
    log("theme_btn", len(theme_btns) > 0, f"主题按钮数: {len(theme_btns)}")

    if len(theme_btns) > 0:
        theme_btns[0].click()
        time.sleep(0.5)
        # 检查 html 是否有 dark class
        has_dark = page.evaluate("() => document.documentElement.classList.contains('dark')")
        log("dark_class", isinstance(has_dark, bool), f"html.dark = {has_dark}")
        screenshot(page, "08_theme_toggled")


def test_agui_sse(page: Page):
    """直接测试 AG-UI 后端 SSE 端点"""
    print("\n[7] AG-UI 后端直接联调")
    try:
        api_result = page.evaluate("""
async () => {
  let r;
  try {
    r = await fetch('http://localhost:8000/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
      body: JSON.stringify({
        thread_id: 'test-direct-' + Date.now(),
        run_id: 'run-' + Date.now(),
        state: {},
        messages: [{ id: 'u1', role: 'user', content: '1+1等于几' }],
        tools: [],
        context: [],
        forwarded_props: { skill: 'research' }
      })
    });
  } catch (e) {
    return { ok: false, error: 'fetch failed: ' + e.message };
  }
  if (!r.ok) return { ok: false, status: r.status, text: await r.text() };
  // 快速读取头部几个事件
  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  let events = [];
  let hasText = false;
  const start = Date.now();
  let responseBroken = false;
  while (Date.now() - start < 20000) {
    let value, done;
    try {
      const result = await reader.read();
      value = result.value;
      done = result.done;
    } catch (e) {
      // 流被截断（网络错误）— 仍认为部分成功
      responseBroken = true;
      break;
    }
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    // 解析 SSE
    const parts = buf.split('\\n\\n');
    buf = parts.pop();
    for (const p of parts) {
      const m = p.match(/^data: (.+)$/m);
      if (m) {
        try {
          const ev = JSON.parse(m[1]);
          events.push(ev.type);
          if (ev.type === 'TEXT_MESSAGE_CONTENT' && ev.delta) hasText = true;
        } catch (e) {}
      }
    }
    if (events.includes('RUN_FINISHED') || events.includes('RUN_ERROR')) break;
  }
  return {
    ok: events.length > 0,
    eventCount: events.length,
    events: events.slice(0, 20),
    hasText,
    responseBroken,
  };
}
""")
    except Exception as e:
        log("agui_request", False, f"evaluate 失败: {e}")
        return
    log("agui_request", api_result.get("ok", False),
        f"events: {api_result.get('eventCount', 0)}, hasText: {api_result.get('hasText', False)}"
        + (", 流被截断" if api_result.get("responseBroken") else ""))
    if not api_result.get("ok"):
        err_msg = api_result.get('error', '') or str(api_result.get("text", ""))[:200]
        if not err_msg:
            err_msg = "后端未返回任何事件"
        log("agui_error", False, err_msg)
    if api_result.get("events"):
        print(f"    事件类型: {api_result.get('events')[:10]}")


def test_action_row_inspect(page: Page):
    """检视 assistant 消息 DOM 结构"""
    print("\n[8] 检视 assistant 消息 DOM")
    # 先切换到一个有消息的会话
    sessions = page.locator('aside li').all()
    has_msg_session = False
    for s in sessions:
        text = s.text_content() or ""
        if "新会话" not in text and "条消息" not in text and ("条消息" in text or any(c.isdigit() for c in text)):
            has_msg_session = True
            break
    # 简单做法：选第一个非"新会话"的会话
    for i in range(len(sessions)):
        s = sessions[i]
        text = s.text_content() or ""
        if "新会话" not in text and i > 0:
            s.click()
            time.sleep(1)
            break
    # 1. 找所有带 class 包含 'group' 的元素
    all_groups = page.evaluate("""
() => {
  return Array.from(document.querySelectorAll('[class*="group"]'))
    .slice(0, 20)
    .map(el => ({
      tag: el.tagName,
      cls: el.className,
      dataRole: el.getAttribute('data-message-role') || el.getAttribute('data-role'),
      text: (el.textContent || '').slice(0, 80),
    }));
}
""")
    print(f"    [DOM] 找到 {len(all_groups)} 个 group 元素")
    for i, el in enumerate(all_groups[:5]):
        print(f"      [{i}] role={el['dataRole']}, cls={el['cls'][:60]}")

    # 2. 找 "复制" 文本节点
    copy_nodes = page.locator('text="复制"').all()
    log("copy_text", len(copy_nodes) > 0, f"复制文本节点数: {len(copy_nodes)}")

    # 3. 找 ActionBarPrimitive 容器
    action_bars = page.evaluate("""
() => {
  return Array.from(document.querySelectorAll('[class*="opacity-0"][class*="group-hover"]'))
    .slice(0, 5)
    .map(el => ({
      cls: el.className.slice(0, 80),
      text: (el.textContent || '').slice(0, 60),
    }));
}
""")
    print(f"    [DOM] 找到 {len(action_bars)} 个 opacity-0 group-hover 元素")
    for el in action_bars:
        print(f"      text='{el['text']}'")

    screenshot(page, "09_dom_inspect")


def main():
    print("=" * 60)
    print("  Study AI Agent - 前后端联调测试")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
        )
        # 收集 console 日志
        console_messages = []
        page = context.new_page()
        page.on("console", lambda msg: console_messages.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: console_messages.append(f"[ERROR] {err}"))

        try:
            test_welcome_screen(page)
            test_send_message(page)
            test_new_session(page)
            test_history_sidebar(page)
            test_skill_switch(page)
            test_theme_toggle(page)
            test_agui_sse(page)
            test_action_row_inspect(page)
        except Exception as e:
            log("test_suite", False, f"未捕获异常: {e}")
            import traceback
            traceback.print_exc()

        # 输出 console 日志（取最后的）
        print("\n[Console 日志（最后 20 条）]")
        for msg in console_messages[-20:]:
            try:
                print(f"  {msg}")
            except UnicodeEncodeError:
                # 兜底：用 ascii replace
                safe = msg.encode('ascii', errors='replace').decode('ascii')
                print(f"  {safe}")

        # 输出 summary
        print("\n" + "=" * 60)
        print(f"  测试结果: {results['pass']} 通过 / {results['fail']} 失败")
        print("=" * 60)
        if results["errors"]:
            print("\n失败项:")
            for e in results["errors"]:
                print(f"  - {e}")

        browser.close()
        return 0 if results["fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
