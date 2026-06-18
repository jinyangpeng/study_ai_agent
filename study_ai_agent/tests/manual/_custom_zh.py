import re
import sys
sys.path.insert(0, ".")

# 直接调 detector 函数, 不用 PIIMiddleware wrapper (因为 wrapper 要求 builtin type)
def detect_custom(regex, text):
    return [{"value": m.group()} for m in re.finditer(regex, text)]

cases = [
    ("phone_cn",  r"1[3-9]\d{9}",                                  "电话13800138000，"),
    ("phone_cn",  r"1[3-9]\d{9}",                                  "电话 13800138000，"),
    ("id_card_cn", r"\d{17}[\dXx]",                                "身份证110101199003078888，"),
    ("api_key",   r"sk-[a-zA-Z0-9]{32}",                           "key=sk-abcdefghijklmnopqrstuvwxyz012345，"),
    ("api_key",   r"sk-[a-zA-Z0-9]{32}",                           "给sk-abcdefghijklmnopqrstuvwxyz012345，"),
]

for name, rgx, text in cases:
    n = len(detect_custom(rgx, text))
    print(f"  {name:12s}  n={n}  {text!r}")