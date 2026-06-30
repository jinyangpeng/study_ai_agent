"""Live test: PII should be redacted in state.messages after /api/chat."""
import urllib.request
import urllib.error
import json
import socket

socket.setdefaulttimeout(8)

tid = "pii_live_test_2"
text = "帮我发一份email给test@test.com，帮我向他问好并祝他生日快乐。"

# 1. /api/chat
data = json.dumps({"message": text, "thread_id": tid}).encode()
req = urllib.request.Request(
    "http://127.0.0.1:8000/api/chat",
    data=data,
    headers={"Content-Type": "application/json"},
)
print(f"[1] sending to /api/chat: {text!r}")
try:
    urllib.request.urlopen(req, timeout=8)
    print("    chat returned OK")
except Exception as e:
    print(f"    chat failed (LLM may be down): {type(e).__name__}: {e}")

# 2. /threads/{tid}/state
print(f"\n[2] reading /threads/{tid}/state")
try:
    r = urllib.request.urlopen(f"http://127.0.0.1:8000/threads/{tid}/state", timeout=5)
    state = json.loads(r.read().decode())
except urllib.error.HTTPError as e:
    print(f"    HTTP {e.code}: {e.read().decode()[:200]}")
    raise SystemExit(1)

# 3. print messages
print("\n[3] messages in thread state:")
for m in state.get("messages", []):
    role = m.get("role", "?")
    content = m.get("content", "")
    if isinstance(content, list):
        content = " ".join(p.get("text", "") for p in content if isinstance(p, dict))
    print(f"    [{role:8s}] {content[:200]!r}")

# 4. verdict
print("\n[4] verdict:")
all_content = json.dumps(state, ensure_ascii=False)
raw = "test@test.com" in all_content
red = "[REDACTED_EMAIL]" in all_content
print(f"    'test@test.com' in state: {raw}")
print(f"    '[REDACTED_EMAIL]' in state: {red}")
print(f"    => {'FAIL: PII NOT redacted in state' if raw else 'OK: PII redacted' if red else 'AMBIGUOUS'}")
