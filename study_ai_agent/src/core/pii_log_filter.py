# -*- coding: utf-8 -*-
"""PII 日志过滤器（#36）—— 给日志记录做 PII 脱敏，防止 PII 落盘。

设计
----
* :class:`PIILogFilter` 是 :mod:`logging.Filter` 子类，在日志记录写出前
  对 ``record.getMessage()`` 返回的格式化消息做正则替换
* 复用 :mod:`src.core.pii_config` 的 ``PII_KEYWORDS`` 配置，与 LLM 层
  PII 中间件用同一套规则
* 只做 ``redact`` / ``mask`` / ``hash`` 三种策略（``block`` 在日志层
  降级为 ``redact``，不能抛异常中断日志）
* 通过 ``settings.PII_LOG_REDACT`` 控制开关（默认开）

使用::

    from src.core.pii_log_filter import PIILogFilter
    handler.addFilter(PIILogFilter())

    # 或直接调 redact_text
    from src.core.pii_log_filter import redact_text
    safe = redact_text("联系我: 13800138000")  # "联系我: [REDACTED_PHONE_CN]"
"""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

from src.config.settings import settings
from src.core.pii_config import PII_KEYWORDS

logger = logging.getLogger(__name__)


#: 特异性优先级 —— 更具体的 PII 类型先匹配，避免被宽泛类型抢匹配。
#: 例如 id_card_cn (18 位含 X) 比 credit_card (13-19 位纯数字) 更具体，
#: 必须先匹配，否则身份证号会被 credit_card 的正则吃掉。
_PRIORITY: dict[str, int] = {
    "id_card_cn": 0,
    "phone_cn": 1,
    "api_key": 2,
    "email": 3,
    "credit_card": 4,
    "ip": 5,
    "mac_address": 6,
    "url": 7,
}


def _build_patterns() -> list[tuple[str, re.Pattern, str]]:
    """从 PII_KEYWORDS 构建 (pii_type, compiled_pattern, strategy) 列表。

    内置类型（email / credit_card / ip / mac_address / url）如果没有
    ``detector`` 字段，用 LangChain PIIMiddleware 的内置正则。但日志层
    不依赖 LangChain，所以这里要求所有类型都有 ``detector`` 或用兜底正则。

    返回的列表按 :data:`_PRIORITY` 排序，更具体的类型排在前面。
    """
    # 内置类型的兜底正则（与 pii_keywords.json 的 detector 对齐）
    builtin_detectors: dict[str, str] = {
        "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "credit_card": r"\b[0-9]{13,19}\b",
        "ip": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        "mac_address": r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b",
        "url": r"https?://[^\s<>\"']+",
    }

    patterns: list[tuple[str, re.Pattern, str]] = []
    for kw in PII_KEYWORDS:
        pii_type = kw.get("pii_type", "")
        if not pii_type:
            continue
        detector = kw.get("detector") or builtin_detectors.get(pii_type, "")
        if not detector:
            continue
        strategy = kw.get("strategy", "redact")
        try:
            patterns.append((pii_type, re.compile(detector), strategy))
        except re.error as exc:
            logger.warning("PII 日志过滤器: 正则编译失败 (type=%s): %s", pii_type, exc)

    # 按特异性排序：更具体的类型先匹配
    patterns.sort(key=lambda p: _PRIORITY.get(p[0], 99))
    return patterns


#: 模块级编译后的正则列表（import 时构建一次）
_PATTERNS: list[tuple[str, re.Pattern, str]] = _build_patterns()


def redact_text(text: Any) -> str:
    """对文本做 PII 脱敏（redact / mask / hash）。

    :param text: 任意对象（会先 ``str()``）
    :returns: 脱敏后的字符串

    策略：
    * ``redact`` → ``[REDACTED_TYPE]``
    * ``mask`` → 保留前 4 后 4，中间用 ``*`` 填充（至少 4 个）
    * ``hash`` → ``<type_hash:前8位>``
    * ``block`` → 日志层降级为 ``redact``（不能抛异常）
    """
    if not settings.PII_LOG_REDACT:
        return str(text)

    s = str(text)
    if not s:
        return s

    for pii_type, pattern, strategy in _PATTERNS:
        if strategy == "redact" or strategy == "block":
            replacement = f"[REDACTED_{pii_type.upper()}]"
            s = pattern.sub(replacement, s)
        elif strategy == "mask":
            def _mask(match):
                matched = match.group(0)
                if len(matched) <= 8:
                    return "*" * len(matched)
                return matched[:4] + "*" * (len(matched) - 8) + matched[-4:]
            s = pattern.sub(_mask, s)
        elif strategy == "hash":
            def _hash(match):
                matched = match.group(0)
                h = hashlib.md5(matched.encode("utf-8")).hexdigest()[:8]
                return f"<{pii_type}_hash:{h}>"
            s = pattern.sub(_hash, s)
    return s


class PIILogFilter(logging.Filter):
    """日志过滤器：对每条日志记录的格式化消息做 PII 脱敏。

    挂到 handler 上后，所有经过该 handler 的日志都会被脱敏。
    通过 ``settings.PII_LOG_REDACT`` 控制开关。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if not settings.PII_LOG_REDACT:
            return True

        # 脱敏 record.msg（格式化模板）和 record.args（参数）
        # 注意：record.getMessage() 会用 msg % args 拼接，
        # 我们需要在拼接前分别脱敏，避免格式化字符串被破坏。
        try:
            if isinstance(record.msg, str):
                record.msg = redact_text(record.msg)
            if record.args:
                if isinstance(record.args, dict):
                    record.args = {k: redact_text(v) for k, v in record.args.items()}
                elif isinstance(record.args, tuple):
                    record.args = tuple(redact_text(a) for a in record.args)
        except Exception as exc:
            # 脱敏失败不能阻塞日志输出，降级为原样输出
            logger.debug("PII 日志脱敏失败: %s", exc)

        return True


__all__ = [
    "PIILogFilter",
    "redact_text",
]
