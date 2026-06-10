"""Middleware 注册表 - 按类别聚合 middleware 列表。

展开顺序是有讲究的：每一层只做一件明确的事。

顺序设计（自上而下是 LangGraph ``create_agent`` 运行时内的生命周期顺序）：

    1. SECURITY      - 在其它任何层看到内容之前就拦截 / 改写敏感内容
                        （PII、prompt injection）
    2. CONTEXT       - 加时间戳、角色前置
    3. VALIDATION    - per-tool 长度 / 格式规则
    4. TRANSFORMATION - 规范化空白、限制响应长度
    5. HUMAN_IN_LOOP - 对危险工具做审批门禁
    6. LOGGING       - 记录每个 hook，方便调试
    7. ERROR         - 兜底异常处理
    8. PERSISTENCE   - 写入历史存储
    9. ROUTING       - 记录失败（实际的切换由 wrapper 完成）
   10. TESTING       - 记录调用序列，方便断言

这个顺序是有意为之：先安全（拦截坏输入），再上下文（丰富），再校验 /
变换（塑形），再 HITL（拦截危险工具），然后是横切关注点（日志、错误、
持久化、路由），最后是测试插桩，让它能记录其它层实际做了什么。
"""
# -*- coding: utf-8 -*-
from __future__ import annotations

from src.core.middleware.context_middleware import CONTEXT_MIDDLEWARES
from src.core.middleware.error_middleware import ERROR_MIDDLEWARES
from src.core.middleware.human_in_loop_middleware import HUMAN_IN_LOOP_MIDDLEWARES
from src.core.middleware.logging_middleware import LOGGING_MIDDLEWARES
from src.core.middleware.persistence_middleware import PERSISTENCE_MIDDLEWARES
from src.core.middleware.routing_middleware import ROUTING_MIDDLEWARES
from src.core.middleware.security_middleware import SECURITY_MIDDLEWARES
from src.core.middleware.testing_middleware import TESTING_MIDDLEWARES
from src.core.middleware.transformation_middleware import TRANSFORMATION_MIDDLEWARES
from src.core.middleware.validation_middleware import VALIDATION_MIDDLEWARES

# 一个展开好的扁平 list，按上面文档的顺序排列。``create_agent`` 在 agent
# 构建时遍历这个 list。
ALL_MIDDLEWARES = (
    SECURITY_MIDDLEWARES         # 1. 拦截 / 脱敏 PII、prompt injection
    + CONTEXT_MIDDLEWARES        # 2. 时间戳 + 角色前置
    + VALIDATION_MIDDLEWARES     # 3. per-tool 长度 / 格式规则
    + TRANSFORMATION_MIDDLEWARES # 4. 空白规范化、限制响应长度
    + HUMAN_IN_LOOP_MIDDLEWARES  # 5. 危险工具的审批门禁
    + LOGGING_MIDDLEWARES        # 6. 控制台 + 文件日志
    + ERROR_MIDDLEWARES          # 7. 兜底异常处理
    + PERSISTENCE_MIDDLEWARES    # 8. history.jsonl 写入
    + ROUTING_MIDDLEWARES        # 9. 失败登记
    + TESTING_MIDDLEWARES        # 10. 仅测试用插桩
)

# ``BASE_MIDDLEWARES`` 是上面 *去掉* HITL 闸门的版本。skill 在 executor 构建
# 时各自 append 一个 :class:`HumanInTheLoopMiddleware`（用 skill 的 per-tool
# 策略配置），所以 HITL 槽位是 per-skill 的，永远不会出现在共享 list 里。
BASE_MIDDLEWARES = (
    SECURITY_MIDDLEWARES
    + CONTEXT_MIDDLEWARES
    + VALIDATION_MIDDLEWARES
    + TRANSFORMATION_MIDDLEWARES
    + LOGGING_MIDDLEWARES
    + ERROR_MIDDLEWARES
    + PERSISTENCE_MIDDLEWARES
    + ROUTING_MIDDLEWARES
    + TESTING_MIDDLEWARES
)


__all__ = [
    "ALL_MIDDLEWARES",
    "BASE_MIDDLEWARES",
    "LOGGING_MIDDLEWARES",
    "SECURITY_MIDDLEWARES",
    "CONTEXT_MIDDLEWARES",
    "ERROR_MIDDLEWARES",
    "TRANSFORMATION_MIDDLEWARES",
    "HUMAN_IN_LOOP_MIDDLEWARES",
    "VALIDATION_MIDDLEWARES",
    "PERSISTENCE_MIDDLEWARES",
    "ROUTING_MIDDLEWARES",
    "TESTING_MIDDLEWARES",
]
