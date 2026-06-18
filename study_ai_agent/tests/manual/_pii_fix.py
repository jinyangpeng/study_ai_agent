"""Verify fix: lookaround-based detector."""
import sys, re
sys.path.insert(0, ".")
from langchain.agents.middleware import PIIMiddleware

# 方案: lookaround 替代 \b, 只在「前/后字符不是 email 字符集」时允许
custom_re = r"(?<![a-zA-Z0-9._%+-])[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?![a-zA-Z0-9._%+-])"

# 注入自定义 detector
m = PIIMiddleware("email", strategy="redact", detector=custom_re, apply_to_input=True)

cases = [
    ("test@test.com",                                  "expected 1"),
    ("给test@test.com",                                "expected 1 (was 0, bug)"),
    ("给test@test.com，",                              "expected 1 (was 0, bug)"),
    ("email给test@test.com",                           "expected 1 (was 0, bug)"),
    ("My email is test@example.com",                   "expected 1 (works)"),
    ("张三的邮箱是 zhang@test.com",                     "expected 1 (works)"),
    ("test@test.com,",                                 "expected 1 (works)"),
    ("给 test@test.com，",                              "expected 1 (works)"),
    ("notanemail",                                     "expected 0"),
    ("test @ test.com",                                "expected 0 (with spaces)"),
    ("test@te",                                        "expected 0 (incomplete)"),
    ("emailfoo@bar.com",                               "expected 1 (foo is part of local)"),
    ("foo bar test@test.com baz",                      "expected 1"),
]

print("Using custom detector with lookaround:")
all_pass = True
for text, expected in cases:
    n = len(m.detector(text))
    expected_n = 1 if "expected 1" in expected else 0
    status = "OK  " if n == expected_n else "FAIL"
    if n != expected_n: all_pass = False
    print(f"  [{status}] {n} match(es)  {expected:32s}  {text!r}")

print()
print("ALL PASS" if all_pass else "SOME FAILED")