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
    DASHSCOPE_BASE_URL: str = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    ZAI_BASE_URL: str = os.getenv("ZAI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/")
    QIANFAN_BASE_URL: str = os.getenv("QIANFAN_BASE_URL", "https://qianfan.baidubce.com/v2")

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

    # ---- PostgreSQL（langgraph checkpointer 后端）----
    # 连接信息：默认指本地开发库。生产环境通过环境变量覆盖。
    # 单机开发：POSTGRES_HOST=localhost
    # 容器编排：POSTGRES_HOST=postgres  （docker compose 服务名）
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "postgres")
    POSTGRES_SCHEMA: str = os.getenv("POSTGRES_SCHEMA", "langgraph_checkpoints")
    # 连接池（AsyncConnectionPool）
    POSTGRES_POOL_MIN_SIZE: int = int(os.getenv("POSTGRES_POOL_MIN_SIZE", "2"))
    POSTGRES_POOL_MAX_SIZE: int = int(os.getenv("POSTGRES_POOL_MAX_SIZE", "10"))
    POSTGRES_POOL_TIMEOUT: float = float(os.getenv("POSTGRES_POOL_TIMEOUT", "30"))
    # 池子健康自检 + 主动回收：防"僵尸连接"导致 PoolTimeout。
    #   CHECK=true      —— 每次 getconn 前跑 SELECT 1，坏连接丢弃重建
    #   MAX_IDLE=600    —— 闲置 10 分钟的连接主动关掉（防服务端 idle-in-tx 超时）
    #   MAX_LIFETIME=3600 —— 强制 1 小时重建一次（不论是否闲置）
    POSTGRES_POOL_CHECK: bool = os.getenv("POSTGRES_POOL_CHECK", "true").lower() in ("1", "true", "yes", "y", "on")
    POSTGRES_POOL_MAX_IDLE: float = float(os.getenv("POSTGRES_POOL_MAX_IDLE", "600"))
    POSTGRES_POOL_MAX_LIFETIME: float = float(os.getenv("POSTGRES_POOL_MAX_LIFETIME", "3600"))
    # Windows 必开：libpq TCP keepalive 探测死连接。
    # Linux 上 PG 服务端 keepalive 默认开着，但客户端 DSN 不开等于没开。
    POSTGRES_KEEPALIVES: int = int(os.getenv("POSTGRES_KEEPALIVES", "1"))
    POSTGRES_KEEPALIVES_IDLE: int = int(os.getenv("POSTGRES_KEEPALIVES_IDLE", "60"))
    POSTGRES_KEEPALIVES_INTERVAL: int = int(os.getenv("POSTGRES_KEEPALIVES_INTERVAL", "10"))
    POSTGRES_KEEPALIVES_COUNT: int = int(os.getenv("POSTGRES_KEEPALIVES_COUNT", "5"))
    # checkpointer 后端选择：
    #   postgres —— AsyncPostgresSaver + 连接池（生产推荐）
    #   memory   —— InMemorySaver（本地无 DB 时回退，仅 dev）
    CHECKPOINTER_BACKEND: str = os.getenv("CHECKPOINTER_BACKEND", "postgres")

    # ---- LangGraph 运行时 ----
    # 控制 PERA / Reflection 这类有循环边的图最多走多少步。
    # LangGraph 默认 25，工具频繁失败时 LLM 反复重试会过早撞顶（GraphRecursionError）。
    # 75 大约够 PERA 5-6 轮 revise + Reflection 5 轮 refine + buffer。
    LANGGRAPH_RECURSION_LIMIT: int = int(os.getenv("LANGGRAPH_RECURSION_LIMIT", "75"))


@lru_cache
def get_settings() -> Settings:
    """返回缓存的 :class:`Settings` 实例（lru_cache 等价于 singleton）。"""
    return Settings()


settings = get_settings()

__all__ = ["Settings", "get_settings", "settings"]
