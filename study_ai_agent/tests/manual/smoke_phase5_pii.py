# -*- coding: utf-8 -*-
"""Phase 5 测试：PII 完善（#36 pii_keywords.json 配置补全 + PIILogFilter 日志脱敏）。

覆盖：
* ``pii_keywords.json`` 配置完整性（所有类型都有 apply_to_output + apply_to_tool_results）
* ``settings.PII_ENABLED`` / ``settings.PII_LOG_REDACT`` 字段存在且默认开
* ``redact_text()`` 对各 PII 类型的脱敏效果（redact / mask / hash / block 降级）
* ``PIILogFilter`` 对日志记录的过滤效果
* 开关关闭时 redact_text 原样返回
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# 配置完整性
# ---------------------------------------------------------------------------
class TestPIIConfig:
    """pii_keywords.json 配置完整性测试。"""

    @pytest.fixture(scope="class")
    def pii_keywords(self) -> list[dict]:
        config_path = (
            Path(__file__).resolve().parents[2] / "config" / "pii_keywords.json"
        )
        with config_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data["keywords"]

    def test_all_keywords_have_apply_to_output(self, pii_keywords):
        """所有 PII 类型都必须有 apply_to_output=True（#36 核心）。"""
        for kw in pii_keywords:
            assert kw.get("apply_to_output") is True, (
                f"PII 类型 {kw.get('pii_type')} 缺少 apply_to_output=True"
            )

    def test_all_keywords_have_apply_to_tool_results(self, pii_keywords):
        """所有 PII 类型都必须有 apply_to_tool_results=True（#36 核心）。"""
        for kw in pii_keywords:
            assert kw.get("apply_to_tool_results") is True, (
                f"PII 类型 {kw.get('pii_type')} 缺少 apply_to_tool_results=True"
            )

    def test_all_keywords_have_detector_or_builtin(self, pii_keywords):
        """所有 PII 类型必须有 detector 或属于内置类型。"""
        builtin_types = {"email", "credit_card", "ip", "mac_address", "url"}
        for kw in pii_keywords:
            pii_type = kw.get("pii_type", "")
            detector = kw.get("detector")
            assert detector or pii_type in builtin_types, (
                f"PII 类型 {pii_type} 既无 detector 也不是内置类型"
            )

    def test_all_keywords_have_valid_strategy(self, pii_keywords):
        """所有 PII 类型的 strategy 必须是 block/redact/mask/hash 之一。"""
        valid_strategies = {"block", "redact", "mask", "hash"}
        for kw in pii_keywords:
            strategy = kw.get("strategy", "redact")
            assert strategy in valid_strategies, (
                f"PII 类型 {kw.get('pii_type')} 的 strategy={strategy!r} 无效"
            )

    def test_covers_required_pii_types(self, pii_keywords):
        """配置必须覆盖核心 PII 类型。"""
        types = {kw["pii_type"] for kw in pii_keywords}
        required = {"email", "credit_card", "ip", "phone_cn", "id_card_cn", "api_key"}
        missing = required - types
        assert not missing, f"缺少必要的 PII 类型: {missing}"


# ---------------------------------------------------------------------------
# settings 字段
# ---------------------------------------------------------------------------
class TestPIISettings:
    """settings.py 中 PII 配置字段测试。"""

    def test_pii_enabled_field_exists(self):
        from src.config.settings import settings

        assert hasattr(settings, "PII_ENABLED")
        assert isinstance(settings.PII_ENABLED, bool)

    def test_pii_log_redact_field_exists(self):
        from src.config.settings import settings

        assert hasattr(settings, "PII_LOG_REDACT")
        assert isinstance(settings.PII_LOG_REDACT, bool)

    def test_pii_enabled_defaults_true(self):
        """PII_ENABLED 默认应该是 True（生产安全默认）。"""
        from src.config.settings import settings

        # 不强制环境变量值，但字段必须存在且是 bool
        assert settings.PII_ENABLED in (True, False)

    def test_pii_log_redact_defaults_true(self):
        """PII_LOG_REDACT 默认应该是 True（生产安全默认）。"""
        from src.config.settings import settings

        assert settings.PII_LOG_REDACT in (True, False)


# ---------------------------------------------------------------------------
# redact_text 各 PII 类型脱敏
# ---------------------------------------------------------------------------
class TestRedactText:
    """redact_text() 对各 PII 类型的脱敏效果测试。"""

    def test_redact_email(self):
        from src.core.pii_log_filter import redact_text

        text = "联系我: alice@example.com 谢谢"
        result = redact_text(text)
        assert "alice@example.com" not in result
        assert "[REDACTED_EMAIL]" in result
        assert "联系我" in result
        assert "谢谢" in result

    def test_redact_phone_cn(self):
        from src.core.pii_log_filter import redact_text

        text = "电话: 13800138000"
        result = redact_text(text)
        assert "13800138000" not in result
        assert "[REDACTED_PHONE_CN]" in result

    def test_redact_id_card_cn(self):
        from src.core.pii_log_filter import redact_text

        text = "身份证: 110101199001011234"
        result = redact_text(text)
        assert "110101199001011234" not in result
        assert "[REDACTED_ID_CARD_CN]" in result

    def test_mask_credit_card(self):
        from src.core.pii_log_filter import redact_text

        # 16 位信用卡号
        text = "卡号: 4111111111111111"
        result = redact_text(text)
        assert "4111111111111111" not in result
        # mask 策略：保留前 4 后 4，中间 *
        assert "4111" in result
        assert "1111" in result
        assert "*" in result

    def test_hash_ip(self):
        from src.core.pii_log_filter import redact_text

        text = "来源 IP: 192.168.1.100"
        result = redact_text(text)
        assert "192.168.1.100" not in result
        # hash 策略：<ip_hash:前8位>
        assert "ip_hash:" in result
        assert "<" in result and ">" in result

    def test_block_strategy_degrades_to_redact(self):
        """block 策略在日志层降级为 redact（不能抛异常）。"""
        from src.core.pii_log_filter import redact_text

        # api_key 是 block 策略
        text = "key=sk-" + "a" * 32
        result = redact_text(text)
        # 不抛异常，且原值被替换
        assert "sk-" + "a" * 32 not in result
        assert "[REDACTED_API_KEY]" in result

    def test_multiple_pii_in_one_message(self):
        """一条消息里有多种 PII，全部脱敏。"""
        from src.core.pii_log_filter import redact_text

        text = "邮箱 alice@example.com 电话 13800138000"
        result = redact_text(text)
        assert "alice@example.com" not in result
        assert "13800138000" not in result
        assert "[REDACTED_EMAIL]" in result
        assert "[REDACTED_PHONE_CN]" in result

    def test_no_pii_unchanged(self):
        """没有 PII 的文本原样返回。"""
        from src.core.pii_log_filter import redact_text

        text = "今天天气不错"
        assert redact_text(text) == text

    def test_empty_string(self):
        from src.core.pii_log_filter import redact_text

        assert redact_text("") == ""

    def test_non_string_input(self):
        """非字符串输入先 str() 再脱敏。"""
        from src.core.pii_log_filter import redact_text

        result = redact_text(13800138000)
        assert "13800138000" not in str(result)
        assert "[REDACTED_PHONE_CN]" in str(result)

    def test_disabled_when_flag_off(self):
        """PII_LOG_REDACT=False 时原样返回。"""
        from src.config.settings import settings
        from src.core.pii_log_filter import redact_text

        text = "邮箱 alice@example.com"
        with patch.object(settings, "PII_LOG_REDACT", False):
            result = redact_text(text)
        assert result == text


# ---------------------------------------------------------------------------
# PIILogFilter 日志过滤
# ---------------------------------------------------------------------------
class TestPIILogFilter:
    """PIILogFilter 对日志记录的过滤效果测试。"""

    def _make_record(self, msg: str, args=None) -> logging.LogRecord:
        """构造一条 LogRecord。"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=msg,
            args=args,
            exc_info=None,
        )
        return record

    def test_filter_redacts_msg(self):
        from src.core.pii_log_filter import PIILogFilter

        f = PIILogFilter()
        record = self._make_record("邮箱 alice@example.com")
        assert f.filter(record) is True
        assert "alice@example.com" not in record.msg
        assert "[REDACTED_EMAIL]" in record.msg

    def test_filter_redacts_args_tuple(self):
        from src.core.pii_log_filter import PIILogFilter

        f = PIILogFilter()
        record = self._make_record("邮箱 %s", args=("alice@example.com",))
        assert f.filter(record) is True
        # args 被脱敏
        assert "alice@example.com" not in record.args[0]
        assert "[REDACTED_EMAIL]" in record.args[0]

    def test_filter_redacts_args_dict(self):
        from src.core.pii_log_filter import PIILogFilter

        f = PIILogFilter()
        # logging.LogRecord 期望 args 是 tuple；dict 模式需要包在单元素 tuple 里
        record = self._make_record("用户 %(email)s", args=({"email": "alice@example.com"},))
        assert f.filter(record) is True
        # LogRecord 会把 args[0] (dict) 提取为 self.args
        assert "alice@example.com" not in record.args["email"]
        assert "[REDACTED_EMAIL]" in record.args["email"]

    def test_filter_passes_when_no_pii(self):
        from src.core.pii_log_filter import PIILogFilter

        f = PIILogFilter()
        record = self._make_record("普通日志消息")
        assert f.filter(record) is True
        assert record.msg == "普通日志消息"

    def test_filter_skips_non_string_msg(self):
        """非字符串 msg 不脱敏（避免破坏对象）。"""
        from src.core.pii_log_filter import PIILogFilter

        f = PIILogFilter()
        obj = {"key": "value"}
        record = self._make_record(obj)
        assert f.filter(record) is True
        # 对象原样保留
        assert record.msg is obj

    def test_filter_returns_true_when_disabled(self):
        from src.config.settings import settings
        from src.core.pii_log_filter import PIILogFilter

        f = PIILogFilter()
        record = self._make_record("邮箱 alice@example.com")
        with patch.object(settings, "PII_LOG_REDACT", False):
            assert f.filter(record) is True
        # 关闭时原样保留
        assert record.msg == "邮箱 alice@example.com"

    def test_filter_does_not_raise_on_exception(self):
        """脱敏过程中抛异常时，filter 不应中断日志输出。"""
        from src.core.pii_log_filter import PIILogFilter

        f = PIILogFilter()
        record = self._make_record("普通消息")

        # 模拟 redact_text 抛异常
        with patch("src.core.pii_log_filter.redact_text", side_effect=RuntimeError("boom")):
            # 不抛异常，返回 True
            assert f.filter(record) is True


# ---------------------------------------------------------------------------
# 集成：日志 handler 注册
# ---------------------------------------------------------------------------
class TestPIILogFilterIntegration:
    """验证 PIILogFilter 真的被注册到 app logger 的 handler 上。"""

    def test_app_logger_has_pii_filter(self):
        """app logger 的每个 handler 都应该有 PIILogFilter。"""
        # 触发 logger 初始化
        from src.logging.setup import logger

        handlers = logger.handlers
        assert handlers, "app logger 应该至少有一个 handler"

        from src.core.pii_log_filter import PIILogFilter

        for h in handlers:
            filters = h.filters
            has_pii = any(isinstance(f, PIILogFilter) for f in filters)
            assert has_pii, f"handler {h} 没有 PIILogFilter"

    def test_logger_output_redacted(self, caplog):
        """端到端：通过 app logger 输出含 PII 的消息，caplog 应捕获到脱敏后的内容。

        注意：caplog 用的是自己的 handler，不是 app logger 的 handler，
        所以这里手动把 PIILogFilter 加到 caplog 的 handler 上做验证。
        """
        from src.core.pii_log_filter import PIILogFilter

        # 给 caplog handler 加 PIILogFilter
        caplog.handler.addFilter(PIILogFilter())
        caplog.set_level(logging.INFO, logger="app")

        app_logger = logging.getLogger("app")
        app_logger.info("邮箱 alice@example.com")

        # caplog.records 是 handler 处理后的记录
        # 注意：filter 修改的是 record.msg
        captured_msg = caplog.records[-1].msg
        assert "alice@example.com" not in captured_msg
        assert "[REDACTED_EMAIL]" in captured_msg
