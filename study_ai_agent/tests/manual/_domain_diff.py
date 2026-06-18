"""Compare test@test.com vs test@example.com vs other test domains."""
import sys
sys.path.insert(0, ".")
from langchain.agents.middleware import PIIMiddleware

m = PIIMiddleware("email", strategy="redact", apply_to_input=True)

cases = [
    "test@test.com",
    "test@example.com",
    "test@gmail.com",
    "test@qq.com",
    "test@a.b",
    "test@localhost",
    "test@example.org",
    "abc@def.cn",
    "我的邮箱是 test@test.com",
    "我的邮箱是 test@example.com",
    "发邮件给 test@test.com",
    "发邮件给 test@example.com",
    "email is test@test.com",  # 全英文 + @
    "email is test@example.com",
]

for c in cases:
    matches = m.detector(c)
    print(f"{len(matches):2d}  {c!r}")