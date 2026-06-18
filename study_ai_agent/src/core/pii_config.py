# -*- coding: utf-8 -*-
"""PII 配置加载器 - 从 JSON 配置加载 PII 规则。"""

import json
from pathlib import Path

# 路径解析: src/core/pii_config.py
#   .parent            -> src/core/
#   .parent.parent     -> src/
#   .parent.parent.parent -> <项目根>   (config/ 在这里)
_CONFIG_FILE = Path(__file__).resolve().parent.parent.parent / "config" / "pii_keywords.json"


def _load_pii_keywords() -> list[dict]:
    """从 JSON 配置文件加载 PII 关键字。"""
    if not _CONFIG_FILE.exists():
        return []
    with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f).get("keywords", [])


PII_KEYWORDS = _load_pii_keywords()

__all__ = ["PII_KEYWORDS"]
