"""应用级 logger。

暴露一个 :data:`logger` 实例（名为 ``"app"``），同时配置
stdout handler 和滚动文件 handler（落在 ``<project_root>/logs/app.log``）。
通过 :mod:`src.logging` 引入::

    from src.logging import logger
    logger.info("ready")
"""
import logging
import sys
from pathlib import Path

from src.config import settings

# 日志文件落在 <project_root>/logs/。在 import 阶段就创建好，
# 调用方不用关心目录是否存在。
LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_DIR.mkdir(exist_ok=True)


def _setup_logger() -> logging.Logger:
    """构造（或返回已缓存的）应用 logger。"""
    logger = logging.getLogger("app")
    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    # 如果这个函数被跑多次（例如测试套件重 import），复用已有的 handler。
    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # stdout handler —— 对 ``docker logs`` / ``journalctl`` 友好。
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    # 文件 handler —— 持久化记录，调试时方便 ``tail -f``。
    file_handler = logging.FileHandler(
        LOG_DIR / "app.log", encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger


logger = _setup_logger()
