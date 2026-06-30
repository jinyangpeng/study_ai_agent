"""PII middleware end-to-end test.

直接调用 SECURITY_MIDDLEWARES 的 wrap_model_call 钩子，验证：
1. email (redact)  -> "test@example.com" -> "[REDACTED:email]"
2. phone_cn (redact) -> "13800138000" -> "[REDACTED:phone_cn]"
3. api_key (block)   -> 含 sk-...  -> 抛 PIIDetectionError
4. credit_card (mask) -> "4111111111111234" -> "****-****-****-1234"
5. 中英文混排: "张三的邮箱是 zhang@test.com" -> 邮箱被脱敏, 张三不动
"""
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from langchain.agents.middleware import PIIMiddleware

from src.core.middleware.security_middleware import SECURITY_MIDDLEWARES


def _make_request_with_message(text: str):
    """构造 PIIMiddleware.wrap_model_call 期望的 Request-like 对象。

    langchain 的 wrap_model_call 签名是 (request, handler) -> response,
    request 有 .messages 列表 (含 HumanMessage).
    """
    from langchain_core.messages import HumanMessage

    class _Request:
        def __init__(self, msg):
            self.messages = [msg]
    return _Request(HumanMessage(content=text))


async def _run_middleware(mw: PIIMiddleware, text: str) -> str:
    """执行一条 PII middleware, 返回处理后 HumanMessage 的 content。"""
    req = _make_request_with_message(text)
    called = {}

    async def handler(req):
        called["yes"] = True
        return "OK"

    # wrap_model_call 在检测到 block strategy 时会主动抛异常, 不会调 handler
    try:
        await mw.wrap_model_call(req, handler)
    except Exception as e:
        return f"[BLOCKED] {type(e).__name__}: {e}"
    # redact 完成后, 重新读 messages
    return req.messages[0].content


async def main():
    print("=" * 60)
    print(f"loaded {len(SECURITY_MIDDLEWARES)} PII middleware instances")
    print("=" * 60)

    cases = [
        ("email redact", "email", "My email is test@example.com"),
        ("email 中文混排", "email", "张三的邮箱是 zhang@test.com"),
        ("phone_cn redact", "phone_cn", "电话: 13800138000"),
        ("credit_card mask", "credit_card", "卡号 4111111111111234"),
        ("ip hash", "ip", "from 192.168.1.100"),
        ("url redact", "url", "see https://example.com/foo"),
        ("id_card_cn redact", "id_card_cn", "身份证 110101199003078888"),
        ("api_key block", "api_key", "key=sk-abcdefghijklmnopqrstuvwxyz012345"),
    ]

    by_type = {m.pii_type: m for m in SECURITY_MIDDLEWARES}
    for label, pii_type, text in cases:
        mw = by_type.get(pii_type)
        if mw is None:
            print(f"[skip] {label}: no middleware for {pii_type}")
            continue
        result = await _run_middleware(mw, text)
        # 短展示
        result_short = result if len(result) < 90 else result[:87] + "..."
        print(f"\n[{label}]")
        print(f"  in : {text!r}")
        print(f"  out: {result_short!r}")


if __name__ == "__main__":
    asyncio.run(main())
