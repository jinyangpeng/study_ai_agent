"""PII middleware end-to-end test - uses real before_model hook."""
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
        return text  # 未命中
    return result["messages"][0].content


def main():
    print(f"loaded {len(SECURITY_MIDDLEWARES)} PII middlewares")
    print("=" * 75)
    cases = [
        ("email",       "My email is test@example.com"),
        ("email",       "张三的邮箱是 zhang@test.com"),
        ("phone_cn",    "电话: 13800138000"),
        ("credit_card", "卡号 4111111111111111"),
        ("ip",          "from 192.168.1.100"),
        ("url",         "see https://example.com/foo"),
        ("id_card_cn",  "身份证 110101199003078888"),
        ("api_key",     "key=sk-abcdefghijklmnopqrstuvwxyz012345"),
    ]
    by_type = {m.pii_type: m for m in SECURITY_MIDDLEWARES}
    for pii_type, text in cases:
        mw = by_type.get(pii_type)
        if not mw:
            print(f"[skip] no {pii_type}"); continue
        out = run_one(mw, text)
        changed = "  " if out == text else ">>"
        print(f"[{pii_type:13s}] {changed} in : {text!r}")
        print(f"{' '*16}    out: {out!r}")
        print()


if __name__ == "__main__":
    main()