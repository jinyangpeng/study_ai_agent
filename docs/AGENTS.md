# 扩展指南（AGENTS）

如何给项目新增一个 **Skill** / **Provider** / **Tool** / **Middleware**。

> 假设你已经读过 [ARCHITECTURE.md](ARCHITECTURE.md)，知道 PPAS 图、中间件顺序、AG-UI 挂载点是怎么回事。

---

## 1. 新增一个 Skill

**适用场景**：新做一个垂直场景的智能体，比如"数据分析" / "运维排障"。

### 1.1 创建 skill 文件

在 [`study_ai_agent/src/skills/`](../study_ai_agent/src/skills/) 下新建 `data_analysis.py`，
继承 `BaseSkill`：

```python
# study_ai_agent/src/skills/data_analysis.py
"""Data Analysis Skill - 面向数据查询 / 指标解释任务。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.tools import COMPUTATION_TOOLS, DATABASE_TOOLS, INFO_TOOLS
from src.skills.base_skill import BaseSkill

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool


class DataAnalysisSkill(BaseSkill):
    """数据分析智能体。"""

    id: str = "data_analysis"
    name: str = "数据分析"
    description: str = (
        "面向 SQL 查询 / 指标解释 / 简单可视化建议任务的智能体。"
        "数据库写操作会触发人工审批。"
    )

    # ---- 前端欢迎区 ----
    quick_prompts: list[dict[str, str]] = [
        {
            "icon": "BarChart3",
            "title": "指标解释",
            "description": "一句话说清",
            "prompt": "帮我用一句话解释 DAU / WAU / MAU 的区别。",
        },
        # ... 4 个左右
    ]

    # ---- 三个节点的 prompt ----
    planner_prompt: str = "..."
    executor_prompt: str = "..."
    reviewer_prompt: str = "..."

    @property
    def tools(self) -> list["BaseTool"]:
        return list(COMPUTATION_TOOLS) + list(DATABASE_TOOLS) + list(INFO_TOOLS)

    @property
    def hitl_rules(self) -> dict[str, dict[str, list[str]]]:
        # 标记破坏性工具需要审批
        return {
            "sql_write": {"allowed_decisions": ["approve", "reject"]},
            "shell_exec": {"allowed_decisions": ["approve", "edit", "reject"]},
        }


__all__ = ["DataAnalysisSkill"]
```

### 1.2 注册到 SKILL_REGISTRY

```python
# study_ai_agent/src/skills/__init__.py
from src.skills.data_analysis import DataAnalysisSkill

SKILL_REGISTRY: dict[str, "SkillModule"] = {
    "coding":       CodingSkill(),
    "qa":           QASkill(),
    "research":     ResearchSkill(),
    "data_analysis": DataAnalysisSkill(),   # ← 新增
}
```

> 不需要改 server / graph / 前端 —— `_compiled_graph_for` / `/skeletons` / SkillContext 会自动发现。

### 1.3 前端可选：在 Layout 里加专属图标

[`study_ai_agent_ui/src/components/Layout/Layout.tsx`](../study_ai_agent_ui/src/components/Layout/Layout.tsx) 的
`iconForSkeleton(id)` 加一个分支：

```tsx
function iconForSkeleton(id: string | undefined): typeof Code2 {
  switch (id) {
    case 'coding':        return Code2;
    case 'research':      return Compass;
    case 'data_analysis': return BarChart3;   // ← 新增
    default:              return Sparkles;
  }
}
```

### 1.4 自检

```bash
just dev
curl http://localhost:8000/skeletons | jq '.skeletons[].id'
# 应输出 4 个：coding / qa / research / data_analysis
```

---

## 2. 新增一个模型供应商

**适用场景**：接 OpenAI / 硅基流动 / 月之暗面 等新厂商。

### 2.1 创建 provider wrapper

在 [`study_ai_agent/src/providers/`](../study_ai_agent/src/providers/) 下新建 `moonshot.py`：

```python
"""Moonshot AI 供应商。"""
from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from src.config import settings
from src.providers.base import BaseModelProvider, ModelConfig


class MoonshotProvider(BaseModelProvider):
    """Moonshot chat 模型。"""

    def build_chat(self, config: ModelConfig) -> BaseChatModel:
        if not settings.MOONSHOT_API_KEY:
            raise ValueError("MOONSHOT_API_KEY not set")
        from langchain_openai import ChatOpenAI   # Moonshot 走 OpenAI 兼容协议

        return ChatOpenAI(
            model=config.model_name or "moonshot-v1-8k",
            api_key=settings.MOONSHOT_API_KEY,
            base_url="https://api.moonshot.cn/v1",
            streaming=True,
        )


__all__ = ["MoonshotProvider"]
```

### 2.2 在 settings 加 API Key 字段

```python
# study_ai_agent/src/config/settings.py
class Settings(BaseSettings):
    # ...
    MOONSHOT_API_KEY: str = os.getenv("MOONSHOT_API_KEY", "")
```

### 2.3 注册到 model_factory

```python
# study_ai_agent/src/core/model_factory.py
from src.providers import MoonshotProvider

_PROVIDER_REGISTRY: dict[str, tuple[Type[ChatModelBuilder], str]] = {
    "qianfan":   (QianfanProvider,  "QIANFAN_API_KEY"),
    "zhipuai":   (ZhipuAIProvider,  "ZAI_API_KEY"),
    "deepseek":  (DeepSeekProvider, "DEEPSEEK_API_KEY"),
    "qwen":      (QwenProvider,     "DASHSCOPE_API_KEY"),
    "moonshot":  (MoonshotProvider, "MOONSHOT_API_KEY"),   # ← 新增
}
```

### 2.4 在 AgentConfig 加 per-provider 配置

```python
# study_ai_agent/src/core/config.py
class AgentConfig(BaseModel):
    strategy: str = "priority"
    qianfan:   ModelConfig = ModelConfig(model_name="ERNIE-Bot",     priority=10)
    zhipuai:   ModelConfig = ModelConfig(model_name="glm-5.1",       priority=20)
    deepseek:  ModelConfig = ModelConfig(model_name="deepseek-chat", priority=30)
    qwen:      ModelConfig = ModelConfig(model_name="qwen-turbo",    priority=40)
    moonshot:  ModelConfig = ModelConfig(model_name="moonshot-v1-8k", priority=50)  # ← 新增
```

### 2.5 自检

```bash
# 在 .env.development 填 MOONSHOT_API_KEY=...
just dev
# 启动日志应出现 "MOONSHOT API key configured, available"
```

---

## 3. 新增一个工具

**适用场景**：给 coding skill 加个 `git_diff`；给 research skill 加个 `arxiv_search`。

### 3.1 找到对应分类

[`study_ai_agent/src/core/tools/__init__.py`](../study_ai_agent/src/core/tools/__init__.py) 暴露了 10 个分类 list：

| 分类 | list 名 | 典型场景 |
| --- | --- | --- |
| 信息查询 | `INFO_TOOLS` | 时间、IP、汇率… |
| 搜索 | `SEARCH_TOOLS` | 网页搜索、图片搜索 |
| 知识 | `KNOWLEDGE_TOOLS` | Wikipedia、Arxiv |
| 计算 | `COMPUTATION_TOOLS` | 数值计算、单位换算 |
| 文件 | `FILE_TOOLS` | 读写、搜索、git |
| 数据库 | `DATABASE_TOOLS` | SQL 查询 |
| 通信 | `COMMUNICATION_TOOLS` | 邮件、IM |
| 集成 | `INTEGRATION_TOOLS` | 三方 API |
| 安全 | `SAFETY_TOOLS` | PII、prompt 注入检测 |
| 工具 | `UTILITY_TOOLS` | 杂项 |

如果都不合适，可以新开一个分类（在 `_TOOL_MODULES` 里 append）。

### 3.2 写一个工具

在对应分类文件加一个 typed 函数（LangChain 1.x 会从签名 + docstring 自动包装）：

```python
# study_ai_agent/src/core/tools/file_tools.py
from langchain_core.tools import tool

@tool
def git_diff(file: str, base: str = "HEAD") -> str:
    """返回 file 相对 base ref 的 diff。

    Args:
        file: 仓库内文件路径（相对仓库根）。
        base: git ref，默认 HEAD。

    Returns:
        unified diff 字符串；出错时返回错误信息（不抛异常）。
    """
    import subprocess
    try:
        out = subprocess.check_output(
            ["git", "diff", base, "--", file],
            stderr=subprocess.STDOUT, text=True,
        )
        return out or "(no diff)"
    except subprocess.CalledProcessError as e:
        return f"[git diff error] {e.output}"
```

然后追加到文件底部的 `FILE_TOOLS` list：

```python
FILE_TOOLS = [
    read_file,
    write_file,
    edit_file,
    delete_file,
    git_diff,   # ← 新增
]
```

> 工具可以是 `def` / `async def` / `@tool` 装饰；缺三方依赖时该分类自动降级为 `[]`，
> 不影响其它工具与 agent 启动。

### 3.3 挂到 skill

```python
# study_ai_agent/src/skills/coding.py
@property
def tools(self) -> list["BaseTool"]:
    return list(FILE_TOOLS) + list(SEARCH_TOOLS)  # git_diff 已包含在 FILE_TOOLS
```

### 3.4 自检

```bash
curl http://localhost:8000/skeletons | jq '.skeletons[] | select(.id=="coding").tool_count'
# tool_count 应该 +1
```

### 3.5 让新工具支持代理

如果你的新 tool 需要发 HTTP（搜索、抓数据、调三方 API 等），参考
[`src/core/tools/proxy.py`](../study_ai_agent/src/core/tools/proxy.py) 的设计：

1. **包装 langchain tool 类**，把 `_run` / `_arun` 用
   `with use_temp_env_proxy("<tool_name>"):` 包一层：

   ```python
   # src/core/tools/<your_tool>.py
   from langchain_community.tools import BaseTool
   from src.core.tools.proxy import use_temp_env_proxy

   class _ProxyAwareMyTool(MyTool):
       def _run(self, *args, **kwargs):
           with use_temp_env_proxy("my_tool"):  # 必须与 .name 一致
               return super()._run(*args, **kwargs)
       async def _arun(self, *args, **kwargs):
           with use_temp_env_proxy("my_tool"):
               return await super()._arun(*args, **kwargs)
   ```

2. **拿到准确 tool name**：用 `MyTool(...).name`，确保白名单里写的字符串
   和它完全一致（**注意大小写**和下划线 / 连字符）。`DuckDuckGoSearchResults`
   的 `.name` 实际是 `"duckduckgo_results_json"` 而不是类名。

3. **写好白名单示例**：在 [`study_ai_agent/.env.development`](../study_ai_agent/.env.development)
   的 `TOOL_PROXY_WHITELIST` 注释里加上你的 tool 名（不要解开 —— 默认直连），
   方便用户复制。

4. **不强制走代理**：包 `use_temp_env_proxy` 之后，user 不配白名单时
   `with` 块什么也不做，行为与父类完全一致（无额外开销）。

完整实现可参考 [`src/core/tools/knowledge_tools.py`](../study_ai_agent/src/core/tools/knowledge_tools.py)
或 [`src/core/tools/search_tools.py`](../study_ai_agent/src/core/tools/search_tools.py)。

---

## 4. 新增一个中间件

**适用场景**：想在所有 run 上加一个统一的"调用次数限制"。

### 4.1 创建中间件文件

在 [`study_ai_agent/src/core/middleware/`](../study_ai_agent/src/core/middleware/) 下新建
`rate_limit_middleware.py`：

```python
"""调用频率限制中间件。"""
from __future__ import annotations

from langchain.agents.middleware import AgentMiddleware


class RateLimitMiddleware(AgentMiddleware):
    """对 tool_call 次数做软限制（超过 N 抛 ToolException 让 reviewer 回环）。"""

    def __init__(self, max_calls: int = 20):
        self.max_calls = max_calls
        self._calls = 0

    def after_tool_call(self, *args, **kwargs):  # 简化版，请按 LangChain 1.x 实际签名
        self._calls += 1
        if self._calls > self.max_calls:
            raise RuntimeError(f"tool_call count exceeded {self.max_calls}")


RATE_LIMIT_MIDDLEWARES = [RateLimitMiddleware()]
```

### 4.2 在注册表暴露

```python
# study_ai_agent/src/core/middleware/__init__.py
from src.core.middleware.rate_limit_middleware import RATE_LIMIT_MIDDLEWARES

ALL_MIDDLEWARES = (
    SECURITY_MIDDLEWARES
    + CONTEXT_MIDDLEWARES
    + VALIDATION_MIDDLEWARES
    + TRANSFORMATION_MIDDLEWARES
    + RATE_LIMIT_MIDDLEWARES        # ← 插在你想要的位置
    + HUMAN_IN_LOOP_MIDDLEWARES
    + LOGGING_MIDDLEWARES
    + ERROR_MIDDLEWARES
    + PERSISTENCE_MIDDLEWARES
    + ROUTING_MIDDLEWARES
    + TESTING_MIDDLEWARES
)
```

> 中间件顺序是 **设计契约**，详见 [ARCHITECTURE.md §3](ARCHITECTURE.md#3-中间件管线)。
> 插错位置可能让原本应被 Security 拦截的内容溜过去。

---

## 5. 把新组件接到前端

新增 skill / 工具后通常前端不需要改（`/skeletons` 会自动暴露）。

需要前端配合的场景：

| 场景 | 改哪里 |
| --- | --- |
| 新 skill 专属侧栏图标 | `Layout.tsx` 的 `iconForSkeleton` |
| 新增 / 修改快速提示卡 | skill 文件里的 `quick_prompts` |
| 自定义侧信道渲染 | `components/assistant-ui/state-panel.tsx` |
| 展示新增的 `code_changes` | 同上 + `state.code_changes` 在 `AgentState` 已声明 |

---

## 6. 跑回归

```bash
cd study_ai_agent
pytest                                     # 全部
pytest tests/unit/ -k test_your_new_thing  # 你的新增
```

新增 skill / provider / 工具时，**强烈建议**：

- 单元测试放到 `tests/unit/test_<category>.py`
- 集成测试放到 `tests/integration/test_<scenario>.py`
- 一次性诊断脚本放到 `tests/manual/`（不入 CI）
