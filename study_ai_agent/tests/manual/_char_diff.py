import sys
sys.path.insert(0, ".")
from langchain.agents.middleware import PIIMiddleware
m = PIIMiddleware("email")

cases = [
    "test@test.com",
    "给test@test.com",
    "给test@test.com，",
    "给test@test.com.",
    "test@test.com,",  # 半角
    "test@test.com，",  # 全角
    "给 test@test.com",  # 半角空格
    "给 test@test.com，",  # 半角空格 + 全角逗号
    "给test@test.com,",  # 紧贴半角逗号
    "给test@test.com，",  # 紧贴全角逗号
    "邮件给test@test.com",
    "email给test@test.com",
    "emailtest@test.com",
    "test@te",  # 不完整的
    "st.com",
]

for c in cases:
    matches = m.detector(c)
    print(f"{len(matches):2d}  bytes={len(c.encode())}  {c!r}")