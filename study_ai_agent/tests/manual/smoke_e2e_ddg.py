"""端到端：触发 DDG 真实异常，看 safe_tool 能不能让 agent 优雅降级。"""
import json
import sys
import urllib.request
import uuid
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

payload = {
    "thread_id": f"test-{uuid.uuid4()}",
    "run_id": f"run-{uuid.uuid4()}",
    "state": {},
    "messages": [{
        "id": f"m-{uuid.uuid4()}",
        "role": "user",
        "content": "对比dify和coze的优缺点",
    }],
    "tools": [],
    "context": [],
    "forwarded_props": {"skill": "research"},
}

req = urllib.request.Request(
    "http://localhost:8125/",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
    method="POST",
)

try:
    with urllib.request.urlopen(req, timeout=180) as resp:
        print(f"HTTP {resp.status}")
        print()
        events = []
        text_chunks = []
        for raw in resp:
            line = raw.decode("utf-8", errors="replace").rstrip()
            if not line.startswith("data: "):
                continue
            ev = json.loads(line[6:])
            t = ev.get("type", "?")
            events.append(t)
            if t == "TEXT_MESSAGE_CONTENT":
                text_chunks.append(ev.get("delta", "") or ev.get("content", ""))
            elif t == "TOOL_CALL_RESULT":
                content = ev.get("content", "")
                if isinstance(content, str) and content.startswith("{"):
                    try:
                        parsed = json.loads(content)
                        if parsed.get("ok") is False:
                            print(f"  TOOL_CALL_RESULT (error JSON): {parsed['error'][:140]}")
                        else:
                            print(f"  TOOL_CALL_RESULT (success): {content[:140]}")
                    except json.JSONDecodeError:
                        print(f"  TOOL_CALL_RESULT: {content[:140]}")
            elif t == "RUN_ERROR":
                print(f"  RUN_ERROR: {ev.get('message', '')[:200]}")
            elif t == "RUN_FINISHED":
                print("  RUN_FINISHED [ok]")
        print()
        print("=== Event types ===")
        for k, v in Counter(events).most_common():
            print(f"  {k}: {v}")
        if text_chunks:
            full = "".join(text_chunks)
            print()
            print("=== Final assistant text (前 800 字) ===")
            print(full[:800])
except urllib.error.HTTPError as e:
    print(f"HTTP error {e.code}: {e.read().decode()[:500]}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    sys.exit(1)
