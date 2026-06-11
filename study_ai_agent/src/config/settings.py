"""项目配置（基于 pydantic-settings）。"""
# -*- coding: utf-8 -*-
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = os.getenv("ENV", "development")
env_file = BASE_DIR / f".env.{env}"
if not env_file.exists():
    env_file = BASE_DIR / ".env"
load_dotenv(env_file)


class Settings(BaseSettings):
    """应用配置（从环境变量 / .env 加载）。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- 模型 ----
    AGENT_STRATEGY: str = os.getenv("AGENT_STRATEGY", "priority")

    # ---- 各家厂商的 API key ----
    QIANFAN_API_KEY: str = os.getenv("QIANFAN_API_KEY", "")
    ZAI_API_KEY: str = os.getenv("ZAI_API_KEY", "")
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")

    # ---- 各家厂商的 OpenAI 兼容 base URL ----
    # 默认指向厂商官方端点；可通过环境变量覆盖，常见场景：
    #   - 企业内代理 / 网关
    #   - 跨地域加速（华北2 / VPC 内网等）
    #   - 自部署兼容 OpenAI 协议的服务
    # 留空时由对应 provider 的 ``ModelConfig.base_url`` 兜底（通常等于下面默认值）。
    DASHSCOPE_BASE_URL: str = os.getenv(
        "DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    DEEPSEEK_BASE_URL: str = os.getenv(
        "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
    )
    ZAI_BASE_URL: str = os.getenv(
        "ZAI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/"
    )
    QIANFAN_BASE_URL: str = os.getenv(
        "QIANFAN_BASE_URL", "https://qianfan.baidubce.com/v2"
    )

    # ---- 应用 ----
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # ---- 网络类工具的代理控制 ----
    # 默认"全部走直连"，按需在 :mod:`src.core.tools.proxy` 中白名单启用。
    # 设置示例（.env.development）：
    #   TOOL_HTTP_PROXY=http://127.0.0.1:10809
    #   TOOL_PROXY_WHITELIST=wikipedia,duckduckgo_results_json
    # 可选 tool 名（与 langchain ``BaseTool.name`` 一致）：
    #   - wikipedia                （knowledge_tools.py）
    #   - duckduckgo_results_json  （search_tools.py，注意不是 duckduckgo_search）
    # 注意：这里只是把 env 暴露到 settings 里便于统一查阅；实际生效仍走
    # ``src.core.tools.proxy`` 直接读 os.environ。
    TOOL_HTTP_PROXY: str = os.getenv("TOOL_HTTP_PROXY", "") or os.getenv("HTTP_PROXY", "")
    TOOL_PROXY_WHITELIST: str = os.getenv("TOOL_PROXY_WHITELIST", "")


@lru_cache
def get_settings() -> Settings:
    """返回缓存的 :class:`Settings` 实例（lru_cache 等价于 singleton）。"""
    return Settings()


settings = get_settings()

__all__ = ["Settings", "get_settings", "settings"]
