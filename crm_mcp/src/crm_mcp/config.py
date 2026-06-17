"""运行配置（基于 pydantic-settings）。

CRM MCP 服务的所有可调参数都集中在这里，便于通过环境变量覆盖。
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 服务根目录：<repo>/crm_mcp/
BASE_DIR = Path(__file__).resolve().parent.parent.parent
# 模拟数据目录：<repo>/crm_mcp/data/
DEFAULT_DATA_DIR = BASE_DIR / "data"


class Settings(BaseSettings):
    """CRM MCP 服务配置（从环境变量 / .env 加载）。"""

    model_config = SettingsConfigDict(
        env_prefix="CRM_MCP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- 服务监听 ----
    HOST: str = os.getenv("CRM_MCP_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("CRM_MCP_PORT", "8001"))

    # ---- 数据 ----
    # 模拟数据 JSON 文件位置；首次启动时若文件不存在则从 seed 拷贝。
    DATA_FILE: Path = Path(os.getenv("CRM_MCP_DATA_FILE", str(DEFAULT_DATA_DIR / "crm_store.json")))
    # 首次启动使用的种子数据（包内自带）
    SEED_FILE: Path = Path(os.getenv("CRM_MCP_SEED_FILE", str(DEFAULT_DATA_DIR / "crm_seed.json")))

    # ---- 日志 ----
    LOG_LEVEL: str = os.getenv("CRM_MCP_LOG_LEVEL", "INFO")

    # ---- 分页默认值 ----
    DEFAULT_PAGE_SIZE: int = int(os.getenv("CRM_MCP_DEFAULT_PAGE_SIZE", "20"))
    MAX_PAGE_SIZE: int = int(os.getenv("CRM_MCP_MAX_PAGE_SIZE", "100"))


@lru_cache
def get_settings() -> Settings:
    """返回缓存的 :class:`Settings` 实例。"""
    return Settings()


settings = get_settings()

__all__ = ["Settings", "get_settings", "settings", "BASE_DIR", "DEFAULT_DATA_DIR"]
