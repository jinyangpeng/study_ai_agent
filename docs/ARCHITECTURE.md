# 架构设计（ARCHITECTURE）

> 本文档面向二次开发者，解释 **为什么** 这么设计，而不是 **怎么用**。
> 想要跑起来请看 [QUICKSTART.md](QUICKSTART.md)；想新增组件请看 [AGENTS.md](AGENTS.md)。

## 1. 顶层视图

<!-- ARCHITECTURE 占位：docs/assets/architecture-overview.svg 是占位图，正式发布前请替换为正式架构图 -->
![Architecture Overview](assets/architecture-overview.svg)

整个系统被切分成三层：

| 层 | 角色 | 关键依赖 |
| --- | --- | --- |
| 客户端 | 多会话聊天 + 状态面板 + 配置 | Vite / React / assistant-ui / AG-UI SSE |
| 协议层 | 事件模型 / SSE 编码 / LangGraph 适配 | `ag-ui-protocol` / `ag-ui-langgraph` |
| 运行时 | 多 skill 路由 / PPAS 图 / 工具 / 中间件 | LangChain 1.x / LangGraph 1.x / Pydantic 2 |

**核心原则：**

1. **协议与运行时解耦** —— 不绑定 CopilotKit 等私有 SDK，任何 AG-UI 兼容前端都能对接。
2. **Skill 即图** —— 每个 skill 一个独立编译的 `CompiledStateGraph`，互不影响。
3. **模型供应商可插拔** —— `ModelFactory` 是唯一调度点，新增厂商只需注册到 `_PROVIDER_REGISTRY`。
4. **类型贯穿** —— 子 agent 用 `response_format=PydanticModel`，外层 state 用 `TypedDict(total=False)`，侧信道数据直接以 Pydantic 对象流转。

## 2. PPAS 图

四个节点的串行 + 一次回环，是整个项目的核心抽象：

```text
        START
          │
          ▼
      planner          ← 用 create_agent(response_format=Plan)
          │
          ▼
      executor         ← 用 create_agent(tools=skill.tools)
          │
          ▼
      reviewer         ← 用 create_agent(response_format=Review)
          │              │
          ▼              ▼
      aggregator       planner    （reviewer.verdict == "revise" 时回环，
          │                          由 LangGraph recursion_limit 控制上限）
          ▼
         END
```

为什么是 **Planner → Executor → Reviewer → Aggregator**（缩写 PPAS）？

- **Planner**：把模糊用户问题切成 2-6 步可验证步骤，避免 executor 走偏。
- **Executor**：实际调用工具的节点；它的 prompt 引导它按 plan 顺序执行、显式产出侧信道（citations / code_changes）。
- **Reviewer**：用结构化 `Review(verdict, issues, suggestions)` 把"通过 / 重做"做成可路由信号。
- **Aggregator**：把所有轮次输出合并成 `final_answer`，暴露给 AG-UI 前端。

**为什么不直接 `create_agent` 一把梭？**

| 维度 | 单 agent | PPAS |
| --- | --- | --- |
| 工具规模 | 难扩 | 每个 skill 各自挂工具集 |
| 可控性 | 黑盒 | 节点级观测 / 中间件 |
| 回环 | 无 | reviewer → planner |
| 类型安全 | 自由文本 | Pydantic 模型贯穿 |

实现见 [`study_ai_agent/src/core/graph.py`](../study_ai_agent/src/core/graph.py)，
节点构造见 [`study_ai_agent/src/core/nodes.py`](../study_ai_agent/src/core/nodes.py)。

## 3. 中间件管线

`LangChain 1.x` 把 Agent 中间件统一到 `langchain.agents.middleware` 包里，
我们在 [`study_ai_agent/src/core/middleware/__init__.py`](../study_ai_agent/src/core/middleware/__init__.py)
按 **固定顺序** 链式生效：

```text
  1. SECURITY       - PII 脱敏 / prompt injection 拦截
  2. CONTEXT        - 加时间戳、角色前缀
  3. VALIDATION     - per-tool 长度 / 格式校验
  4. TRANSFORMATION - 规范化空白、限制响应长度
  5. HUMAN_IN_LOOP  - 危险工具审批门禁（per-skill 注入）
  6. LOGGING        - 控制台 + 文件日志
  7. ERROR          - 兜底异常
  8. PERSISTENCE    - history.jsonl 落盘
  9. ROUTING        - 失败登记
 10. TESTING        - 调用序列插桩（测试专用）
```

**设计取舍：**

- **顺序即契约** —— Security 必须最先看到原始输入（脱敏后再去 Validation 就晚了）。
- **HITL 是 per-skill 的** —— 共享 `BASE_MIDDLEWARES` 不含 HITL；每个 skill 在 `executor` 构建时按自己的 `hitl_rules` 注入一个 `HumanInTheLoopMiddleware`。
- **不要在 TESTING 里塞业务逻辑** —— 它只在测试模式下启用，避免污染生产 trace。

## 4. Skill 注册表

`SKILL_REGISTRY` 是项目的"业务配置中心"：

```python
# study_ai_agent/src/skills/__init__.py
SKILL_REGISTRY: dict[str, "SkillModule"] = {
    "coding":   CodingSkill(),
    "qa":       QASkill(),
    "research": ResearchSkill(),
}
DEFAULT_SKILL_ID = "research"
```

每个 skill 是 `SkillModule` 的实例，至少声明：

- `id` / `name` / `description`：前端选择器 / 后端 `/skeletons` 用
- `planner_prompt` / `executor_prompt` / `reviewer_prompt`：四个节点的系统提示
- `tools`（property）：该 skill 可见的工具集
- `hitl_rules`（property）：危险工具的审批决策集（`approve` / `edit` / `reject`）
- `quick_prompts`：前端欢迎区的快捷提示卡（`{icon, title, description, prompt}`）

详细扩展教程见 [AGENTS.md](AGENTS.md)。

## 5. 模型供应商调度

`ModelFactory` 是 **唯一** 的供应商决策点，
不写死在 wrapper 里：

```python
# study_ai_agent/src/core/model_factory.py
_PROVIDER_REGISTRY: dict[str, tuple[Type[ChatModelBuilder], str]] = {
    "qianfan":  (QianfanProvider,  "QIANFAN_API_KEY"),
    "zhipuai":  (ZhipuAIProvider,  "ZAI_API_KEY"),
    "deepseek": (DeepSeekProvider, "DEEPSEEK_API_KEY"),
    "qwen":     (QwenProvider,     "DASHSCOPE_API_KEY"),
}
```

调度策略：

- `priority`（默认）：按 `ModelConfig.priority` 升序选，数字小的胜出
- `round_robin`：轮询所有配置了 key 的供应商
- `random`：随机抽

**为什么 wrapper 是无状态类、不是单例？**

避免 `from src.providers import qianfan` 返回"子模块还是单例"的歧义；
按需 `QianfanProvider().build_chat(cfg)` 干净利落。

## 6. AG-UI 挂载

`server.py` 把多个已编译图挂到同一个 `POST /` 端点：

```python
def _agui_agent_for(skill_id: str) -> LangGraphAgent:
    skill, graph = _compiled_graph_for(skill_id)        # 编译图按 skill_id 缓存
    return LangGraphAgent(name=..., description=..., graph=graph)

@app.post("/")
async def run_agui(payload: RunAgentInput, request: Request):
    skill_id = _resolve_skill_id_from_input(payload.model_dump())
    request_agent = _agui_agent_for(skill_id).clone()    # 每请求 clone
    encoder = EventEncoder(accept=request.headers.get("accept"))
    return StreamingResponse(event_generator(), media_type=encoder.get_content_type())
```

几个关键点：

- **skill 来自 `forwarded_props`**：AG-UI 标准字段，缺失回落 `DEFAULT_SKILL_ID`
- **每请求 clone**：避免 `active_run` 在并发 run 之间泄漏
- **SSE 错误兜底**：异常要 yield 一个 `RunErrorEvent` 再正常返回函数，否则浏览器侧会被裸截断为 `ERR_INCOMPLETE_CHUNKED_ENCODING`

## 7. 前端架构

```
┌─────────────────────────────── App ────────────────────────────────┐
│ <Providers>                                                        │
│   ├ <ConfigContext>     — apiBaseUrl / health                      │
│   ├ <SessionContext>    — 多会话 / activeId / messageCount         │
│   ├ <SkillContext>      — /skeletons 拉取 + currentSkill           │
│   └ <AguiStateContext>  — STATE_SNAPSHOT 侧信道                     │
│                                                                   │
│ <Routes>                                                           │
│   ├ /chat     → Layout > HistorySidebar + Chat (Thread + StatePanel)│
│   └ /config   → Layout > Config                                    │
└────────────────────────────────────────────────────────────────────┘
```

数据流：

```text
用户输入
  └─▶ Chat.tsx
        └─▶ useChatController  (基于 assistant-ui useExternalStoreRuntime)
              └─▶ lib/agui/run.ts
                    └─▶ POST /  (AG-UI SSE)
                          └─▶ EventEncoder → 浏览器
                                ├─ TEXT_MESSAGE_*  → Thread 渲染
                                └─ STATE_SNAPSHOT  → AguiStateContext → StatePanel
```

为什么不用 `useLocalRuntime`？它只能跑单会话；我们用 `useExternalStoreRuntime` 实现了多会话，
由 `SessionContext` 持有 active id，切换时清空 `AguiStateContext`。

## 8. 状态契约一览

子 agent → 外层 state → AG-UI 前端，三层都用 Pydantic 模型做类型契约：

| 模型 | 产出者 | 写入位置 | 消费方 |
| --- | --- | --- | --- |
| `Plan` | planner | `state.plan` | executor 节点 + AG-UI `state-panel` |
| `Review` | reviewer | `state.review` | reviewer 之后的条件边 + AG-UI `state-panel` |
| `Citation` | research executor | `state.citations` | research skill 的 AG-UI 引用面板 |
| `CodeChange` | coding executor | `state.code_changes` | coding skill 的 AG-UI diff 面板 |
| `final_answer` (str) | aggregator | `state.final_answer` | AG-UI 的最终消息 |

所有字段都是 `total=False`，每个节点只写自己负责的 key；reducer 用 `add_messages` 合并 `messages`。

## 9. 测试策略

```
tests/
├── unit/          # 纯单测，不依赖外部服务（tools / schemas / ...）
├── llm/           # 需要 API Key；CI 单独跑
├── integration/   # 需要先起后端；测端点 + 事件流
├── manual/        # 一次性诊断脚本，不入 CI
└── http/chat.http # VS Code / IntelliJ HTTP Client 风格 curl
```

`pytest-asyncio` 用 `asyncio_mode = "auto"`，任何 `async def test_xxx` 自动当 async case 跑。

## 10. 设计权衡备忘

| 决策 | 备选 | 选定理由 |
| --- | --- | --- |
| LangChain 1.x `create_agent` | Pydantic AI runtime | LangChain 1.x 已统一暴露 Agent + Middleware，类型安全一样好，少一个依赖 |
| 不用 CopilotKit SDK | 官方 AG-UI 协议 | 协议中立，方便对接自家前端或任何 AG-UI 客户端 |
| `InMemorySaver` | Postgres / SQLite checkpointer | 学习项目够用；上线时再换持久化 |
| `round_robin` 按数量均摊 | 按延迟加权 | 学习场景不需要；见 [路线图](../README.md#路线图) |
| 前端 `useExternalStoreRuntime` | `useLocalRuntime` | 多会话支持 |
| 工具分 10 个分类 | 一个 tools.py 大杂烩 | 防御性加载、启动成本可控、缺失依赖降级到空 list |
| `forwarded_props.skill` | URL path / Header | 协议层中立，未来加认证 / 业务字段不挤 path |
