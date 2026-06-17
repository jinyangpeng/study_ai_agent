# study_ai_agent — Python 后端

LangChain 1.x + LangGraph + AG-UI 协议的多智能体运行时。

## 目录

- [快速开始](#快速开始)
- [Docker 启动](#docker-启动)
- [just 命令](#just-命令)
- [运行时架构](#运行时架构)
- [目录结构](#目录结构)
- [配置项](#配置项)
- [HTTP API](#http-api)
- [测试](#测试)
- [故障排查](#故障排查)

## 快速开始

### 1. 准备环境

要求 **Python ≥ 3.10**。

```bash
cd study_ai_agent
python -m venv .venv

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
# POSIX
source .venv/bin/activate
```

### 2. 安装依赖

```bash
# 仅直接依赖 + dev（推荐）
pip install -e ".[dev]"

# 或者用锁文件复现完整环境
pip install -r requirements.txt
```

> `pyproject.toml` 的 `[project.dependencies]` 表达"项目直接用了什么"（24 个），
> `requirements.txt` 是 `pip freeze` 出来的完整锁文件（76+ 个），
> 两者各有定位，详见 [pyproject.toml 顶部注释](pyproject.toml)。

### 3. 配置 API Key

```bash
just env-dev        # 生成 .env.development（生产环境用 just env-prod）
```

编辑 `.env.development`：

```env
ENV=development

# 至少填一个（可同时填多个，由 ModelFactory 决定调度策略）
DASHSCOPE_API_KEY=       # 通义千问
DEEPSEEK_API_KEY=        # DeepSeek
ZAI_API_KEY=             # 智谱 GLM
QIANFAN_API_KEY=         # 千帆

LOG_LEVEL=DEBUG
```

> `.env.*` 已在 `.gitignore` 中，请勿提交。

### 4. 启动

```bash
dev                 # 等价于 ENV=development python main.py
# 或直接
python main.py      # 监听 http://0.0.0.0:8000
```

打开 [http://localhost:8000/health](http://localhost:8000/health) 应返回 `{"status":"ok", ...}`。

## just 命令

```text
just             # 列出所有命令
just init        # 一键初始化（venv + 依赖 + .env）
just venv        # 仅创建虚拟环境
just install     # 安装依赖（pip install -e ".[dev]"）
just dev         # 开发环境运行
just prod        # 生产环境运行
just lint        # ruff check
just fmt         # ruff format
just clean       # 清理 __pycache__、dist、logs…
just env-dev     # 创建 .env.development
just env-prod    # 创建 .env.production
```

> 控制台脚本 `dev` / `prod` / `lint` / `fmt` 来自 [cli/commands.py](cli/commands.py)，
> `pip install -e .` 后即可全局使用。

## 运行时架构

详细图示与事件流见 [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md)，下面是文字版：

```
                ┌─────────── SKILL_REGISTRY (skills/__init__.py) ───────────┐
                │  "coding"   ─┐                                           │
                │  "research" ─┼─→ SkillModule(prompt, tools, hitl_rules)   │
                │  "qa"       ─┘                                           │
                └────────────────────────────┬──────────────────────────────┘
                                             │  build_graph(skill)
                                             ▼
                       ┌─────── CompiledStateGraph (per skill, cached) ───┐
   RunAgentInput ──▶   │  START → plan → execute → review                   │
   (AG-UI POST /)      │                  ↑         │                       │
                       │                  │     approve/revise              │
                       │                  │         │   │                    │
                       │                  └─────────┘   ▼                    │
                       │                              act → END              │
                       └────────────────────────────────────────────────────┘
                                             │
                                             ▼
                                ag_ui_langgraph.LangGraphAgent
                                （每请求 clone，避免 active_run 泄漏）
                                             │
                                             ▼
                            SSE (EventEncoder) → 前端 / 任何 AG-UI 客户端
```

四个节点（`plan` / `execute` / `review` / `act`）都是通过 LangChain 1.x 的
`create_agent(response_format=Plan/Review)` 构造的子 agent，**共用同一个 chat model**。
中间件按 `src/core/middleware/__init__.py` 的顺序链式生效（Security → Context → … → Testing）。

## 目录结构

```
study_ai_agent/
├── src/
│   ├── core/
│   │   ├── graph.py               # build_graph(skill) 工厂
│   │   ├── nodes.py               # 四个节点的构造函数 + 路由逻辑
│   │   ├── state.py               # AgentState TypedDict（外层 state）
│   │   ├── schemas.py             # Plan / Review / Citation / CodeChange
│   │   ├── server.py              # FastAPI 入口 + AG-UI 挂载
│   │   ├── model_factory.py       # 供应商调度（priority/round_robin/random）
│   │   ├── pii_config.py          # PII 关键字 / 脱敏策略
│   │   ├── logging_handler.py     # LangChain callback handler
│   │   ├── events.py              # 自定义 AG-UI 事件
│   │   ├── middleware/            # 10 类中间件（security/hitl/logging/...）
│   │   └── tools/                 # 10 类工具（file/search/knowledge/...）
│   ├── skills/                    # 技能定义：coding / research / qa
│   ├── providers/                 # 模型供应商 wrapper
│   ├── config/                    # pydantic-settings 全局配置
│   └── logging/                   # 日志初始化
├── cli/
│   └── commands.py                # dev / prod / lint / fmt
├── tests/
│   ├── unit/                      # 纯单元测试
│   ├── llm/                       # 需要 API Key 的 LLM 测试
│   ├── integration/               # 需要启动后端
│   ├── manual/                    # 一次性诊断脚本（不在 CI 中）
│   ├── http/chat.http             # REST Client 风格 curl 脚本
│   ├── conftest.py
│   └── README.md
├── config/
│   └── pii_keywords.json          # PII 关键字配置（可由用户自定义）
├── pyproject.toml
├── requirements.txt
├── justfile
└── main.py
```

## 配置项

来自 [`src/config/settings.py`](src/config/settings.py)：

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `ENV` | `development` | 决定加载 `.env.development` 还是 `.env.production` |
| `AGENT_STRATEGY` | `priority` | 模型供应商调度：`priority` / `round_robin` / `random` |
| `QIANFAN_API_KEY` | `""` | 千帆 API Key |
| `ZAI_API_KEY` | `""` | 智谱 GLM API Key |
| `DEEPSEEK_API_KEY` | `""` | DeepSeek API Key |
| `DASHSCOPE_API_KEY` | `""` | 阿里通义千问 / DashScope API Key |
| `DASHSCOPE_BASE_URL` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 通义千问 OpenAI 兼容端点，可换企业内网 / 跨地域 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | DeepSeek 端点 |
| `ZAI_BASE_URL` | `https://open.bigmodel.cn/api/paas/v4/` | 智谱 GLM 端点 |
| `QIANFAN_BASE_URL` | `https://qianfan.baidubce.com/v2` | 千帆端点 |
| `TOOL_HTTP_PROXY` | `""` | 网络类工具的代理 URL（如 `http://127.0.0.1:10809`） |
| `TOOL_PROXY_WHITELIST` | `""` | 走代理的 tool 名称白名单，逗号分隔；留空 = 全部直连 |
| `LOG_LEVEL` | `INFO` | 日志级别（`DEBUG` / `INFO` / `WARNING` / `ERROR`） |
| `HOST` | `0.0.0.0` | uvicorn 监听地址 |
| `PORT` | `8000` | uvicorn 监听端口 |

> 至少需要 1 个 LLM API Key，否则 `ModelFactory` 在启动时会打 `ERROR` 级别日志。

### 网络类工具代理

Python 默认不读系统代理。`requests` / `httpx` / `duckduckgo-search` /
`wikipedia` 这几个库都会读 `HTTP_PROXY` / `HTTPS_PROXY` 环境变量。

如果直接在 `.env` 里写 `HTTP_PROXY=...`，会污染所有出网请求（包括 LLM
供应商调用）。本项目提供**按 tool 白名单开代理**的方案：

```env
# 1) 设代理地址
TOOL_HTTP_PROXY=http://127.0.0.1:10809
# 2) 列需要走代理的 tool（与 langchain BaseTool.name 一致）
TOOL_PROXY_WHITELIST=wikipedia,duckduckgo_results_json
```

行为：

- 白名单内的 tool 在 `_run` 调用期间临时把 `HTTP_PROXY` / `HTTPS_PROXY` /
  `http_proxy` / `https_proxy` 注入到 env，调用完立即还原。
- 白名单外的 tool 完全不动 env，照常走直连。
- `TOOL_PROXY_WHITELIST` 为空时即使配了 `TOOL_HTTP_PROXY` 也**不会**走代理。
- 已有同名 `HTTP_PROXY` 也会被临时改写；调用完恢复为原值，**不污染** LLM 供应商。

当前已接入代理感知的工具：

| Tool 名称 | 模块 | 说明 |
| --- | --- | --- |
| `wikipedia` | [`src/core/tools/knowledge_tools.py`](src/core/tools/knowledge_tools.py) | 维基百科查询 |
| `duckduckgo_results_json` | [`src/core/tools/search_tools.py`](src/core/tools/search_tools.py) | DuckDuckGo Web 搜索 |

新加 tool 想支持代理，参考 [`docs/AGENTS.md §3.5`](../docs/AGENTS.md#35-让新工具支持代理)。

实现见 [`src/core/tools/proxy.py`](src/core/tools/proxy.py)。

## HTTP API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/health` | 健康检查 |
| GET | `/skeletons` | 列出已注册 skill（含 prompt 摘要、工具数、HITL 规则数）。前端 `/chat` 左侧选择器使用 |
| POST | `/` | AG-UI 运行端点（SSE 事件流） |
| POST | `/api/chat` | 旧版同步聊天，方便 `curl` 测试 |

### curl 示例

健康检查：

```bash
curl http://localhost:8000/health
```

列出 skill：

```bash
curl http://localhost:8000/skeletons | jq
```

同步聊天（默认 skill = `research`）：

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"用一句话解释 AG-UI 协议","thread_id":"t1","skill":"qa"}'
```

AG-UI SSE 跑通：

```bash
curl -N -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "thread_id":"t1",
    "run_id":"r1",
    "messages":[{"role":"user","content":"你好"}],
    "forwarded_props":{"skill":"research"}
  }'
```

完整脚本见 [`tests/http/chat.http`](tests/http/chat.http)（VS Code REST Client / IntelliJ HTTP Client 可直接打开）。

## 测试

```bash
# 全部
pytest

# 仅单元
pytest tests/unit/

# 仅 LLM（需要至少 1 个 API Key）
pytest tests/llm/

# 集成（需要先启动后端）
uvicorn src.core.server:app &   # 或 `dev`
pytest tests/integration/
```

> 详细分类说明见 [`tests/README.md`](tests/README.md)。

## 故障排查

| 现象 | 可能原因 | 处理 |
| --- | --- | --- |
| `No available model providers!` | 没有任何 LLM API Key | 在 `.env.development` 至少填一个 |
| SSE 流被截断 / `ERR_INCOMPLETE_CHUNKED_ENCODING` | 后端异常未被 `RunErrorEvent` 兜住 | 确认 [`src/core/server.py`](src/core/server.py) 的 try/except 包装；如自修改请保留 RUN_ERROR 兜底 |
| `forwarded_props.skill` 不生效 | payload 字段缺失 | 默认回落 `DEFAULT_SKILL_ID` = `"research"` |
| `langchain_deepseek` / `langchain_openai` 安装失败 | 锁文件过旧 | `pip install --upgrade langchain-deepseek langchain-openai` 后重导 `requirements.txt` |
| `npm run dev` 报 CORS 错 | 前端地址未在 `allow_origins` | 默认 `*`；生产环境请改 [`src/core/server.py`](src/core/server.py) 的 `allow_origins` |

更多调试脚本在 [`tests/manual/`](tests/manual/)（不在 CI 中运行）：

- `diag_connectivity.py` — 探测各供应商连通性
- `dump_model_selection.py` — 打印 `ModelFactory` 选中的供应商
- `test_agui.py` — 直接打 AG-UI 端点的端到端
- `test_providers.py` — 各供应商 smoke test
- `test_zhipu_tool_choice*.py` — 智谱 tool_choice 行为验证

## 许可证

[MIT](../LICENSE) © 2026 boby
