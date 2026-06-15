"""Study AI Agent - 后端服务。

包结构采用 *kernel + skills* 架构：

- src.config     : 环境 / 配置加载
- src.logging    : 日志初始化
- src.providers  : 模型供应商适配器（DeepSeek / Qwen / Qianfan / ZhipuAI / ...）
- src.core       : 共享的智能体内核
    * schemas/state/skill  - 每个智能体共用的类型化契约
    * graph/nodes/server   - Plan-Execute-Review-Act 图（plan / execute / review / act）
    * model_factory        - 多供应商模型选择
    * middleware           - 横切关注点（安全、HITL、日志、...）
    * tools                - 按类别聚合的可复用工具集
- src.skills     : 可插拔的智能体（即 mode）
    * coding    - 软件工程 Agent（读 / 改 / 测，含 HITL 门禁）
    * research  - 深度研究 Agent（搜索 / 抓取 / 综合，纯只读）
"""
