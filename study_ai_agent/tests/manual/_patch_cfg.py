import pathlib
p = pathlib.Path("config/pii_keywords.json")
s = p.read_text(encoding="utf-8")

old_block = """    {
      "pii_type": "email",
      "strategy": "redact",
      "apply_to_input": true,
      "apply_to_output": true,
      "apply_to_tool_results": true
    },
    {
      "pii_type": "credit_card",
      "strategy": "mask",
      "apply_to_input": true,
      "apply_to_output": true
    },
    {
      "pii_type": "ip",
      "strategy": "hash",
      "apply_to_input": true
    },"""

new_block = """    {
      "pii_type": "email",
      "_detector_note": "lookaround 替代 \u005cb \u2014\u2014 Python \u005cb \u57fa\u4e8e ASCII \u005cw\uff0c\u4e0d\u8bc6\u522b\u4e2d\u6587/\u5168\u89d2\u6807\u70b9\uff0c\u4f1a\u8ba9\u300c\u7ed9test@x.com\u300d\u6f0f\u68c0\u3002",
      "detector": "(?<![a-zA-Z0-9._%+-])[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\u005c.[a-zA-Z]{2,}(?![a-zA-Z0-9._%+-])",
      "strategy": "redact",
      "apply_to_input": true,
      "apply_to_output": true,
      "apply_to_tool_results": true
    },
    {
      "pii_type": "credit_card",
      "_detector_note": "lookaround \u66ff\u4ee3 \u005cb \u2014\u2014 \u540c email\uff0c\u5fc5\u987b\u80fd\u8bc6\u522b\u7d27\u8d34\u4e2d\u6587/\u5168\u89d2\u9017\u53f7\u7684\u60c5\u5f62\u3002",
      "detector": "(?<![0-9])[0-9]{13,19}(?![0-9])",
      "strategy": "mask",
      "apply_to_input": true,
      "apply_to_output": true
    },
    {
      "pii_type": "ip",
      "_detector_note": "lookaround \u66ff\u4ee3 \u005cb \u2014\u2014 IPv4\u3002",
      "detector": "(?<![0-9.])(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\u005c.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)(?![0-9.])",
      "strategy": "hash",
      "apply_to_input": true
    },"""

assert old_block in s, "old block not found"
s = s.replace(old_block, new_block)
p.write_text(s, encoding="utf-8")
print("[ok] patched", len(s), "bytes")