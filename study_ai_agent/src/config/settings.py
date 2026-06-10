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

    # ---- 应用 ----
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))


@lru_cache
def get_settings() -> Settings:
    """返回缓存的 :class:`Settings` 实例（lru_cache 等价于 singleton）。"""
    return Settings()


settings = get_settings()

__all__ = ["Settings", "get_settings", "settings"]
