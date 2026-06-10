# study_ai_agent_ui — React 前端

Vite + React 18 + TypeScript + Tailwind CSS + [assistant-ui](https://www.assistant-ui.com/) 的聊天工作台，
通过 [AG-UI](https://docs.ag-ui.com/) SSE 协议与后端通信。

## 目录

- [特性](#特性)
- [快速开始](#快速开始)
- [npm 脚本](#npm-脚本)
- [环境变量](#环境变量)
- [目录结构](#目录结构)
- [关键模块](#关键模块)
- [截图占位](#截图占位)
- [常见问题](#常见问题)

## 特性

- 多会话支持（侧边栏历史 / 新建 / 切换）
- 多智能体（skill）选择器，技能元数据来自后端 `/skeletons`
- 实时 SSE 流式渲染，assistant-ui 驱动
- 状态面板：把后端 `STATE_SNAPSHOT` 里的 `plan` / `review` / `citations` 拆到右侧
- Markdown / 代码高亮（highlight.js）
- 暗色 / 亮色主题（`useTheme`）
- 快捷键：`⌘/Ctrl + K` 新建会话（`useKeyboardShortcuts`）
- 多层 Layout：左导航 → 中历史 → 主聊天 → 右状态面板
- 配置页：`/config` 可临时改 API Base URL（落地到 localStorage）

## 快速开始

要求 **Node.js ≥ 18**。

```bash
cd study_ai_agent_ui
npm install
cp .env.example .env.local   # 可选，下面是默认值
npm run dev                 # http://localhost:3000
```

> 默认 `VITE_API_BASE_URL=http://localhost:8000`，对应后端默认监听地址。
> 后端没起来时左下角会显示 "加载失败"。

### 生产构建

```bash
npm run build       # tsc -b && vite build，输出到 dist/
npm run preview     # 本地预览构建产物
```

## npm 脚本

| 命令 | 说明 |
| --- | --- |
| `npm run dev` | 启动 Vite 开发服务器（端口 3000） |
| `npm run build` | TypeScript 类型检查 + 生产构建 |
| `npm run preview` | 本地预览构建产物 |
| `npm run lint` | ESLint 检查（`eslint .`） |

## 环境变量

通过 Vite 注入，运行时 `import.meta.env.*` 读取，统一封装在 [`src/config/env.ts`](src/config/env.ts)。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `VITE_APP_TITLE` | `Study AI Agent` | 页面标题 |
| `VITE_PORT` | `3000` | 开发服务器端口 |
| `VITE_HOST` | `localhost` | 开发服务器主机 |
| `VITE_API_BASE_URL` | `http://localhost:8000` | 后端基础地址（同时是 `/api/chat` 的 baseURL） |
| `VITE_HEALTH_CHECK_URL` | `http://localhost:8000/health` | 健康检查地址 |

> `.env.local` 已在 `.gitignore` 中。

## 目录结构

```
study_ai_agent_ui/
├── public/                          # 静态资源
├── src/
│   ├── app/                         # 入口
│   │   ├── App.tsx                  # 路由（/chat / /config）
│   │   ├── main.tsx                 # createRoot + Providers
│   │   └── providers.tsx            # 全局 Provider 装配
│   ├── pages/                       # 路由页
│   │   ├── Chat/                    # 聊天页
│   │   └── Config/                  # 系统配置页
│   ├── components/
│   │   ├── Layout/                  # 整体布局（侧边栏 + Topbar + 主区）
│   │   ├── History/                 # 历史会话侧边栏
│   │   ├── ErrorBoundary/           # 错误边界
│   │   └── assistant-ui/            # assistant-ui 自定义组件（Thread / StatePanel / ...）
│   ├── lib/
│   │   ├── agui/                    # AG-UI SSE 适配 + 聊天 controller
│   │   ├── api/                     # 通用 HTTP 封装
│   │   ├── markdown.ts              # Markdown 渲染
│   │   └── utils.ts                 # cn() 等小工具
│   ├── context/                     # React Context
│   │   ├── ConfigContext.tsx        # 后端地址 / 健康状态
│   │   ├── SessionContext.tsx       # 多会话状态
│   │   ├── SkillContext.tsx         # 智能体（skill）列表
│   │   └── AguiStateContext.tsx     # 后端 STATE_SNAPSHOT 状态
│   ├── features/                    # 业务子模块
│   │   ├── config/                  # 配置读写（api + localStorage）
│   │   ├── sessions/                # 会话存储 + 类型
│   │   └── skills/                  # skill API + 类型
│   ├── hooks/                       # 自定义 hooks
│   ├── config/                      # 构建期/启动期 env 配置
│   ├── types/                       # 全局类型
│   ├── index.css                    # Tailwind 入口
│   └── vite-env.d.ts
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
├── postcss.config.js
└── eslint.config.js
```

## 关键模块

### `lib/agui/` — AG-UI 客户端

| 文件 | 角色 |
| --- | --- |
| `sse.ts` | 基于 `fetch` + `ReadableStream` 的 SSE 解析 |
| `events.ts` | AG-UI 事件类型到 UI 消息的归一化 |
| `run.ts` | 一次 run 的发起 + 事件累积 |
| `adapter.ts` | 兼容 assistant-ui `ChatModelAdapter` 旧 API（基于 `useLocalRuntime`） |
| `chat-controller.tsx` | 多会话实现（基于 `useExternalStoreRuntime`） |
| `types.ts` | 共享类型 |
| `index.ts` | 桶导出 |

> 新代码推荐用 `useChatController`；`adapter.ts` 只为兼容旧入口保留。

### `context/` — 全局状态

- `ConfigContext` — 后端 `apiBaseUrl`、健康检查结果，可热更新。
- `SessionContext` — 会话列表、当前活跃会话、消息计数。
- `SkillContext` — 后端 `/skeletons` 拉取的智能体列表 + 当前 skill。
- `AguiStateContext` — 当前 run 结束后端 `STATE_SNAPSHOT` 的 `plan` / `review` / `citations` 等，由 `StatePanel` 消费。

### `components/assistant-ui/`

- `thread.tsx` — assistant-ui `Thread` 定制（消息列表 / 欢迎区 / 快捷提示卡）。
- `state-panel.tsx` — 右侧 `Plan` / `Review` / `Citations` 面板。
- `markdown-text.tsx` — Markdown + 代码高亮渲染。
- `tool-fallback.tsx` — 工具调用渲染兜底。

## 截图占位

> 正式截图请替换为实际效果。建议存到 `docs/assets/screenshots/` 下。

| 场景 | 占位 |
| --- | --- |
| 聊天主界面（多 skill + 状态面板） | ![Chat Main](docs/assets/screenshots/chat-main.png) |
| 切换智能体（coding） | ![Coding Skill](docs/assets/screenshots/skill-coding.png) |
| Plan / Review 状态 | ![State Panel](docs/assets/screenshots/state-panel.png) |
| 系统配置页 | ![Config Page](docs/assets/screenshots/config-page.png) |
| 暗色主题 | ![Dark Theme](docs/assets/screenshots/dark-theme.png) |

## 常见问题

**Q: 前端起来了但 skill 列表是空的？**
A: 看左下角"后端"地址。浏览器打开 `http://localhost:8000/skeletons` 应能看到 JSON。
若 CORS 报错，确认后端 `CORSMiddleware` 的 `allow_origins` 包含前端域名。

**Q: 改了 `VITE_API_BASE_URL` 不生效？**
A: Vite 启动时注入，运行中改需要重启 dev server；或者用 `/config` 页临时切换（走 localStorage）。

**Q: assistant-ui 报 `useExternalStoreRuntime` 找不到？**
A: 确认 `@assistant-ui/react` 版本 ≥ 0.10.50（见 `package.json`）。

**Q: 流式渲染一半就停？**
A: 后端 SSE 异常未 `RunErrorEvent` 兜底会被浏览器当作 `ERR_INCOMPLETE_CHUNKED_ENCODING` 截断。
请保留后端 [`src/core/server.py`](../study_ai_agent/src/core/server.py) 中 `event_generator` 的 try/except。

## 许可证

[MIT](../LICENSE) © 2026 boby
