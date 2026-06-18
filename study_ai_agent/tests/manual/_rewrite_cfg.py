import json, pathlib

# 用纯 Python dict -> json.dump, 自动正确转义
data = {
    "_comment": "PII（个人身份信息）检测配置。修改后重启服务即可生效。",
    "_doc": {
        "fields": {
            "pii_type": "PII 类型名（用于日志和占位符）",
            "strategy": "处理策略: block / redact / mask / hash",
            "detector": "自定义正则（内置类型可省略）",
            "apply_to_input": "是否处理用户输入",
            "apply_to_output": "是否处理模型输出",
            "apply_to_tool_results": "是否处理工具调用结果"
        },
        "builtin_pii_types": ["email", "credit_card", "ip", "mac_address", "url"],
        "strategies": {
            "block": "抛 PIIDetectionError 异常",
            "redact": "替换为 [REDACTED_TYPE]",
            "mask": "部分掩码（如信用卡 ****-****-****-1234）",
            "hash": "确定性哈希（如 <email_hash:a1b2c3d4>）"
        }
    },
    "keywords": [
        {
            "pii_type": "email",
            "_detector_note": "lookaround 替代 \\b —— Python \\b 基于 ASCII \\w，不识别中文/全角标点，会让「给test@x.com」漏检。",
            "detector": "(?<![a-zA-Z0-9._%+-])[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}(?![a-zA-Z0-9._%+-])",
            "strategy": "redact",
            "apply_to_input": True,
            "apply_to_output": True,
            "apply_to_tool_results": True
        },
        {
            "pii_type": "credit_card",
            "_detector_note": "lookaround 替代 \\b —— 同 email，必须能识别紧贴中文/全角逗号的情形。",
            "detector": "(?<![0-9])[0-9]{13,19}(?![0-9])",
            "strategy": "mask",
            "apply_to_input": True,
            "apply_to_output": True
        },
        {
            "pii_type": "ip",
            "_detector_note": "lookaround 替代 \\b —— IPv4。",
            "detector": "(?<![0-9.])(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)(?![0-9.])",
            "strategy": "hash",
            "apply_to_input": True
        },
        {
            "pii_type": "url",
            "strategy": "redact",
            "apply_to_input": True
        },
        {
            "pii_type": "api_key",
            "detector": "sk-[a-zA-Z0-9]{32}",
            "strategy": "block",
            "apply_to_input": True
        },
        {
            "pii_type": "phone_cn",
            "detector": "1[3-9]\\d{9}",
            "strategy": "redact",
            "apply_to_input": True,
            "apply_to_tool_results": True
        },
        {
            "pii_type": "id_card_cn",
            "detector": "\\d{17}[\\dXx]",
            "strategy": "redact",
            "apply_to_input": True
        }
    ]
}

p = pathlib.Path("config/pii_keywords.json")
# 保留原 2 空格 indent + ensure_ascii=False 让中文可读
p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

# 验证
with open(p, encoding="utf-8") as f:
    loaded = json.load(f)
print("[ok] valid JSON,", len(loaded["keywords"]), "rules")
for kw in loaded["keywords"]:
    det = kw.get("detector", "(builtin)")
    print(f"  - {kw['pii_type']:12s}  strategy={kw['strategy']:7s}  detector={det[:60]}...")