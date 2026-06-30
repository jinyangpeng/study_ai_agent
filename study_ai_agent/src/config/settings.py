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
    #: 日志格式：``text``（开发，可读）或 ``json``（生产，ELK/Loki 友好）
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "text")
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

    # ---- MCP 服务（热插拔外部工具服务）----
    # 格式：name1=url1,name2=url2（逗号分隔，每个条目 name=url）。
    # agent 启动时通过 langchain-mcp-adapters 连接每个 server，把它的工具
    # 包装成 BaseTool 注入到对应 skill。server 不可达时降级为空工具集，
    # 不阻塞 agent 启动。
    # 示例：MCP_SERVERS=crm=http://localhost:8001/mcp
    MCP_SERVERS: str = os.getenv("MCP_SERVERS", "")

    # ---- API 限流（#24）----
    # 基于 IP 的滑动窗口限流。生产环境建议前置 Nginx/网关做分布式限流，
    # 这里作为应用层兜底，防单实例被刷爆。
    # RATE_LIMIT_ENABLED=false 时关闭（本地开发默认关）。
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "false").lower() in ("1", "true", "yes", "y", "on")
    #: 每分钟最大请求数（按 IP 计）
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    #: 限流命中的端点前缀（逗号分隔），默认只限写操作端点
    RATE_LIMIT_PATHS: str = os.getenv("RATE_LIMIT_PATHS", "/,/api/chat,/admin/")

    # ---- SSE 心跳（#7）----
    # 长时间无事件时（LLM 思考中、工具执行中）定期发心跳，防代理/防火墙超时断开。
    # SSE_HEARTBEAT_INTERVAL_SECONDS=0 时关闭心跳。
    SSE_HEARTBEAT_INTERVAL_SECONDS: float = float(os.getenv("SSE_HEARTBEAT_INTERVAL_SECONDS", "15"))

    # ---- LangGraph 运行时防护（#25 / #26 / #27）----
    # 消息裁剪（#25）：长对话历史会让 LLM context 爆炸。
    # 每次调 agent 前保留 system + 最近 N 条消息，超出的截掉。
    # MAX_MESSAGES_PER_TURN=0 时关闭裁剪（不推荐生产用）。
    MAX_MESSAGES_PER_TURN: int = int(os.getenv("MAX_MESSAGES_PER_TURN", "50"))
    #: 工具调用超时（#26）：单个工具卡住时强制取消，防 graph 整体挂死。
    #: 单位秒。TOOL_TIMEOUT_SECONDS=0 时关闭超时（不推荐生产用）。
    TOOL_TIMEOUT_SECONDS: float = float(os.getenv("TOOL_TIMEOUT_SECONDS", "60"))
    #: LLM 输出 max_tokens（#27）：防生成过长导致响应慢 / 成本失控。
    #: 0 表示用模型默认值（不显式传 max_tokens）。
    MODEL_MAX_TOKENS: int = int(os.getenv("MODEL_MAX_TOKENS", "4096"))

    # ---- PII 脱敏（#36）----
    # PII_ENABLED=false 时完全关闭 PII 检测（dev 环境可关，prod 必须开）。
    # PII_LOG_REDACT=true 时给日志加 PII 过滤器，防止 PII 落盘到 logs/。
    PII_ENABLED: bool = os.getenv("PII_ENABLED", "true").lower() in ("1", "true", "yes", "y", "on")
    #: 日志层 PII 脱敏开关。关闭后日志会打印原始 PII（仅 dev 调试用）。
    PII_LOG_REDACT: bool = os.getenv("PII_LOG_REDACT", "true").lower() in ("1", "true", "yes", "y", "on")


@lru_cache
def get_settings() -> Settings:
    """返回缓存的 :class:`Settings` 实例（lru_cache 等价于 singleton）。"""
    return Settings()


settings = get_settings()

__all__ = ["Settings", "get_settings", "settings"]
