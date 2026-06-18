"""Live test: PII should be redacted in state.messages after /api/chat."""
import urllib.request, urllib.error, json, socket
socket.setdefaulttimeout(8)
tid = "pii_live_test_3"
text = "帮我发一份email给test@test.com，帮我向他问好并祝他生日快乐。"
data = json.dumps({"message": text, "thread_id": tid}).encode()
req = urllib.request.Request("http://127.0.0.1:8000/api/chat", data=data, headers={"Content-Type": "application/json"})
print(f"[1] sending: {text!r}")
try:
    urllib.request.urlopen(req, timeout=8)
    print("    chat returned OK")
except Exception as e:
    print(f"    chat failed: {type(e).__name__}")
print(f"\n[2] reading state")
try:
    r = urllib.request.urlopen(f"http://127.0.0.1:8000/threads/{tid}/state", timeout=5)
    state = json.loads(r.read().decode())
except urllib.error.HTTPError as e:
    print(f"    HTTP {e.code}: {e.read().decode()[:200]}")
    raise SystemExit(1)
print("\n[3] messages:")
for m in state.get("messages", []):
    role = m.get("role", "?")
    content = m.get("content", "")
    if isinstance(content, list):
        content = " ".join(p.get("text", "") for p in content if isinstance(p, dict))
    print(f"    [{role:8s}] {content[:200]!r}")
print("\n[4] verdict:")
all_content = json.dumps(state, ensure_ascii=False)
raw = "test@test.com" in all_content
red = "[REDACTED_EMAIL]" in all_content
print(f"    raw email in state: {raw}")
print(f"    REDACTED in state: {red}")
print(f"    => {'FAIL' if raw else ('OK' if red else 'AMBIGUOUS')}")