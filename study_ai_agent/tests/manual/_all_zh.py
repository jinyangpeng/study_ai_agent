"""Check all 7 PII types with Chinese-adjacent text."""
import sys
sys.path.insert(0, ".")
from langchain.agents.middleware import PIIMiddleware

cases = [
    # (pii_type, builtin_test, zh_adjacent_test)
    ("email",       "test@example.com",    "给test@example.com，"),
    ("url",         "https://x.com/y",     "给https://x.com/y，"),
    ("ip",          "192.168.1.1",         "从192.168.1.1发"),
    ("credit_card", "4111111111111111",    "卡4111111111111111，"),
    ("phone_cn",    "13800138000",         "电话13800138000，"),
    ("id_card_cn",  "110101199003078888",  "身份证110101199003078888"),
    ("api_key",     "sk-abcdefghijklmnopqrstuvwxyz012345", "key=sk-abcdefghijklmnopqrstuvwxyz012345"),
]

print(f"{'pii_type':12s}  {'standalone':4s}  {'chinese-adjacent':4s}  text")
for pii_type, stand, zh in cases:
    m = PIIMiddleware(pii_type)
    n1 = len(m.detector(stand))
    n2 = len(m.detector(zh))
    flag = "  <-- BUG" if n1 == 1 and n2 == 0 else ""
    print(f"  {pii_type:12s}  {n1:4d}  {n2:4d}{flag}  {zh!r}")