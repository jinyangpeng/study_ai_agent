"""日志包。

re-export 一个应用级的 :data:`logger`，调用方可以直接写::

    from src.logging import logger
    logger.info("hello")
"""

from src.logging.setup import logger

__all__ = ["logger"]
