# -*- coding: utf-8 -*-
"""应用级 logger —— 结构化日志 + 日志轮转 + request_id 注入。

配置
----
* ``LOG_FORMAT=json`` → 输出 JSON（生产环境，ELK/Loki 友好）
* ``LOG_FORMAT=text`` → 输出可读文本（开发环境，默认）
* 文件 handler 用 ``TimedRotatingFileHandler``（按天轮转，保留 14 天）

暴露 :data:`logger` 实例（名为 ``"app"``）::

    from src.logging import logger
    logger.info("ready", extra={"skill": "coding"})
"""

import logging
import logging.handlers
import sys
from pathlib import Path

from src.config import settings
from src.core.middleware.request_id import RequestIdFilter

# 日志文件落在 <project_root>/logs/。在 import 阶段就创建好，
# 调用方不用关心目录是否存在。
LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_DIR.mkdir(exist_ok=True)

#: 文本格式（开发环境）—— 含 request_id 列
_TEXT_FMT = "%(asctime)s | %(levelname)-8s | %(request_id)-12s | %(name)s | %(message)s"
#: JSON 格式字段（生产环境）
_JSON_FMT = "%(asctime)s %(levelname)s %(name)s %(request_id)s %(message)s"


def _make_formatter() -> logging.Formatter:
    """根据 ``settings.LOG_FORMAT`` 构造格式化器。"""
    if settings.LOG_FORMAT.lower() == "json":
        from pythonjsonlogger import json as json_formatter

        return json_formatter.JsonFormatter(
            _JSON_FMT,
            rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
            json_ensure_ascii=False,
        )
    return logging.Formatter(_TEXT_FMT, datefmt="%Y-%m-%d %H:%M:%S")


def _setup_logger() -> logging.Logger:
    """构造（或返回已缓存的）应用 logger。"""
    logger = logging.getLogger("app")
    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    # 如果这个函数被跑多次（例如测试套件重 import），复用已有的 handler。
    if logger.handlers:
        return logger

    formatter = _make_formatter()
    rid_filter = RequestIdFilter()

    # PII 日志过滤器（#36）：对每条日志做 PII 脱敏，防止 PII 落盘。
    # 通过 settings.PII_LOG_REDACT 控制开关（默认开）。
    from src.core.pii_log_filter import PIILogFilter

    pii_filter = PIILogFilter()

    # stdout handler —— 对 ``docker logs`` / ``journalctl`` 友好。
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(rid_filter)
    console_handler.addFilter(pii_filter)
    logger.addHandler(console_handler)

    # 文件 handler —— 按天轮转，保留 14 天，防止磁盘打满。
    file_handler = logging.handlers.TimedRotatingFileHandler(
        LOG_DIR / "app.log",
        when="midnight",
        backupCount=14,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(rid_filter)
    file_handler.addFilter(pii_filter)
    logger.addHandler(file_handler)

    return logger


logger = _setup_logger()
