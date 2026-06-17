"""信息工具 - 实时信息查询。

工具用 ``langchain_community.tools.tool`` 装饰器，这样可以被
``langgraph.prebuilt`` / ``langchain.agents.create_agent`` 自动发现。
可选 import 块保证依赖缺失时 agent 仍能存活（降级为 ``INFO_TOOLS = []``
+ 一条启动 warning）。
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from langchain_community.tools import tool

    @tool
    def weather(city: str) -> str:
        """查询某个城市的天气。

        Args:
            city: 城市名（例如 Beijing、Shanghai）
        """
        return f"The weather in {city} is sunny"

    @tool
    def get_current_time(timezone: str = "Asia/Shanghai") -> str:
        """获取指定时区的当前时间。

        Args:
            timezone: 时区名（默认 Asia/Shanghai）
        """
        return datetime.now().isoformat()

    INFO_TOOLS = [weather, get_current_time]
except ImportError as e:
    logger.warning("info_tools unavailable (missing dependency: %s)", e)
    weather = None  # type: ignore[assignment]
    get_current_time = None  # type: ignore[assignment]
    INFO_TOOLS = []

__all__ = ["INFO_TOOLS", "weather", "get_current_time"]
