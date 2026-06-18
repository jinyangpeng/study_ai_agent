"""Regression: PII must be redacted even when adjacent to Chinese / full-width punctuation.

Bug history: LangChain builtin detector uses \b word boundary, which is
based on ASCII \w ([A-Za-z0-9_]). Chinese chars are NOT \w, so
regex like \b<email>\b fails when email is right next to a Chinese
character (e.g. "给test@x.com"). This file ensures the lookaround-based
custom detectors catch these.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from langchain_core.messages import HumanMessage
from src.core.middleware.security_middleware import SECURITY_MIDDLEWARES


def run_one(mw, text):
    state = {"messages": [HumanMessage(content=text)]}
    try:
        result = mw.before_model(state, None)
    except Exception as e:
        return f"[BLOCKED] {type(e).__name__}"
    if result is None:
        return text
    return result["messages"][0].content


# (pii_type, original, must_NOT_contain, must_contain)
cases = [
    ("email",      "帮我发一份email给test@test.com，帮我向他问好并祝他生日快乐。",
                   "test@test.com", "[REDACTED_EMAIL]"),
    ("email",      "给test@example.com，",
                   "test@example.com", "[REDACTED_EMAIL]"),
    ("email",      "email给abc@gmail.com，",
                   "abc@gmail.com", "[REDACTED_EMAIL]"),
    ("credit_card","卡号4111111111111111，",
                   "4111111111111111", "1111"),  # mask 保留末 4
    ("ip",         "从192.168.1.100发",
                   "192.168.1.100", "ip_hash"),
]

by_type = {m.pii_type: m for m in SECURITY_MIDDLEWARES}
print("=" * 75)
print("REGRESSION: PII adjacent to Chinese / full-width punctuation")
print("=" * 75)
all_pass = True
for pii_type, text, must_not, must_have in cases:
    mw = by_type.get(pii_type)
    if not mw:
        print(f"  [SKIP] no middleware for {pii_type}")
        continue
    out = run_one(mw, text)
    no_pii = must_not not in out
    has_repl = must_have in out
    status = "OK  " if (no_pii and has_repl) else "FAIL"
    if not (no_pii and has_repl):
        all_pass = False
    print(f"  [{status}] [{pii_type:12s}]")
    print(f"         in : {text!r}")
    print(f"         out: {out!r}")
    print()
print("ALL PASS" if all_pass else "SOME FAILED")