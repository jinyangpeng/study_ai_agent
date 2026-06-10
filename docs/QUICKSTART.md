# 快速开始（QUICKSTART）

5 分钟把后端 + 前端跑起来，并能 curl 验证一次 AG-UI SSE 跑通。

## 0. 前置条件

- **Python ≥ 3.10**（[下载](https://www.python.org/downloads/)）
- **Node.js ≥ 18**（[下载](https://nodejs.org/)）
- 至少 1 个 LLM API Key（**DeepSeek / 智谱 GLM / 通义千问 / 千帆** 任一）

> 不填任何 API Key 也可以启动，但所有 LLM 调用都会失败 —— 后端日志会打 `No available model providers`。

## 1. 拉代码

```bash
git clone https://github.com/<your-org>/study_ai_agent.git
cd study_ai_agent
```

## 2. 启动后端

```bash
cd study_ai_agent
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# POSIX
source .venv/bin/activate

pip install -e ".[dev]"

make env-dev
# 编辑 .env.development，至少填一个 LLM 的 API Key
```

启动：

```bash
dev
# 等价于 ENV=development python main.py
# 监听 http://0.0.0.0:8000
```

打开 [http://localhost:8000/health](http://localhost:8000/health)：

```json
{
  "status": "ok",
  "agent": { "name": "study_ai_agent" },
  "protocol": "ag-ui",
  "default_skill": "research"
}
```

## 3. 验证 skill 列表

```bash
curl http://localhost:8000/skeletons | jq
```

应该看到三个 skill：

```json
{
  "default": "research",
  "skeletons": [
    { "id": "coding",   "name": "编程智能体",   "tool_count": 12, ... },
    { "id": "qa",       "name": "智能问答",     "tool_count": 6,  ... },
    { "id": "research", "name": "深度研究智能体", "tool_count": 14, ... }
  ]
}
```

## 4. curl 跑通 AG-UI SSE

```bash
curl -N -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "thread_id":"t1",
    "run_id":"r1",
    "messages":[{"role":"user","content":"用一句话解释 AG-UI 协议"}],
    "forwarded_props":{"skill":"qa"}
  }'
```

你应该看到形如下面的事件流：

```text
event: RUN_STARTED
data: {"thread_id":"t1","run_id":"r1"}

event: TEXT_MESSAGE_START
data: {...}

event: TEXT_MESSAGE_CONTENT
data: {...}

event: TEXT_MESSAGE_END
data: {...}

event: STATE_SNAPSHOT
data: {"plan":{...},"review":{...},"final_answer":"..."}

event: RUN_FINISHED
data: {...}
```

把 `"skill":"qa"` 换成 `"coding"` 或 `"research"` 即可切换智能体。

## 5. 启动前端

新开一个终端：

```bash
cd study_ai_agent_ui
npm install
npm run dev
# http://localhost:3000
```

<!-- QUICKSTART 占位：把 quickstart-chat.png 替换为实际截图 -->
![Quickstart Chat](assets/screenshots/quickstart-chat.png)

打开后会自动跳到 `/chat`，左侧选 skill，主区打字，右侧 StatePanel 会实时更新 `plan` / `review` / `citations`。

如果左下角显示"加载失败"，点击 **系统配置** 调整后端地址（落地到 localStorage）。

## 6. 跑测试

```bash
# 后端
cd study_ai_agent
pytest                  # 全部
pytest tests/unit/      # 仅单元（无需 API Key）
pytest tests/llm/       # 需要 API Key
```

```bash
# 前端
cd ../study_ai_agent_ui
npm run lint
npm run build
```

## 7. 接下来

- 想理解设计 → [ARCHITECTURE.md](ARCHITECTURE.md)
- 想加 Skill / Provider / Tool → [AGENTS.md](AGENTS.md)
- 想贡献代码 → [CONTRIBUTING.md](CONTRIBUTING.md)
