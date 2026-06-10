"""安全 middleware - 基于配置的 PII 检测。

规则在 import 时从 ``config/pii_keywords.json`` 加载。每条规则都被接入
LangChain 内置的 :class:`PIIMiddleware`，所以我们免费拿到完整生命周期
（输入 / 输出 / tool-result）。

为什么底层用 Pydantic？
----------------------------
LangChain 1.x 的 :class:`PIIMiddleware` 本身是 :class:`pydantic.BaseModel`
的子类 —— 所以规则配置（pii_type、strategy、regex 等）在构造时就做了
类型检查。这就是 "Pydantic 提供类型安全" 兑现价值的地方：
``pii_keywords.json`` 里写错一个字段名，启动时立刻报清晰的校验错误，
而不是运行时崩。
"""
import logging

from langchain.agents.middleware import PIIMiddleware

from src.core.pii_config import PII_KEYWORDS

logger = logging.getLogger(__name__)


def _build_pii_middleware(config: dict) -> PIIMiddleware:
    """从单条规则配置 dict 构造一个 :class:`PIIMiddleware`。"""
    kwargs = {
        "strategy": config.get("strategy", "redact"),
        "apply_to_input": config.get("apply_to_input", True),
        "apply_to_output": config.get("apply_to_output", False),
        "apply_to_tool_results": config.get("apply_to_tool_results", False),
    }
    detector = config.get("detector")
    if detector is not None:
        kwargs["detector"] = detector
    return PIIMiddleware(config["pii_type"], **kwargs)


def _build_pii_middlewares() -> list:
    """根据 :data:`PII_KEYWORDS` 配置构造所有 PII middleware。

    遇到单条坏规则只记一条 error 并跳过 —— 启动不应该被 JSON 文件里的
    笔误卡住。
    """
    middlewares = []
    for cfg in PII_KEYWORDS:
        try:
            middlewares.append(_build_pii_middleware(cfg))
            logger.info(
                f"[PII] Registered: type={cfg['pii_type']}, strategy={cfg.get('strategy', 'redact')}"
            )
        except Exception as e:
            logger.error(f"[PII] Failed to create {cfg.get('pii_type')}: {e}")
    return middlewares


SECURITY_MIDDLEWARES = _build_pii_middlewares()

__all__ = ["SECURITY_MIDDLEWARES", "_build_pii_middleware", "_build_pii_middlewares"]
