# Docker 部署指南（DOCKER）

把后端（LangChain + AG-UI）和前端（Vite + nginx）打包成镜像，
用 `docker compose` 一键起一套完整的运行环境。

> 想 5 分钟跑起来？直接看 [QUICKSTART.md §2-Docker](QUICKSTART.md#2-通过-docker-起服务)。

## 1. 文件清单

所有 Docker 部署文件集中在仓库根的 `docker/` 目录，构建上下文统一为**仓库根**
（`docker/docker-compose.yml` 里两个服务的 `context: ..`），由根 `.dockerignore` 裁剪。

| 文件 | 角色 |
| --- | --- |
| `docker/docker-compose.yml` | 一键编排：backend + frontend + 共享网络 |
| `docker/.env.example` → `docker/.env` | compose 启动期注入的环境变量（端口 / API Key / Vite 构建变量） |
| `docker/Dockerfile.backend` | 后端多阶段镜像（deps + runtime） |
| `docker/Dockerfile.frontend` | 前端多阶段镜像（node:20-alpine 构建 + nginx:alpine 托管） |
| `docker/nginx.conf` | nginx 模板：SPA fallback + `/api` 反代 + SSE 友好 |
| `docker/docker-entrypoint.sh` | 渲染 nginx 模板并启动 nginx |
| `.dockerignore`（根） | 构建上下文裁剪（必须放在仓库根才生效） |

## 2. 架构

```text
浏览器  ───▶  :3000 (frontend, nginx:80)
                  │
                  │  /api/* /skeletons / POST /   ── 反代 ──▶  :8000 (backend, uvicorn)
                  │                                                  │
                  └───── 静态 dist/ 由 nginx 直接托管 ──────────────┘
                                                                     │
                                                                     ▼
                                                              AG-UI SSE
```

Docker compose 内部署了 `agent-net` 桥接网络，frontend 容器通过
`http://backend:8000` 访问后端（注意：是 **容器内** 的服务名 `backend`），
而前端构建期注入的 `VITE_API_BASE_URL=http://localhost:8000` 是 **浏览器** 看到的后端地址。

> 这两个 URL 是有意分开的：
>
> - nginx 反代上游用 `backend:8000` 是因为 nginx 在容器内，可以用 compose 服务名直连；
> - 浏览器看不到 `backend` 这个主机名，所以用 `localhost:8000`（前提是后端 8000 端口已暴露到宿主机）。

## 3. 一键启动

### 3.1 准备 `.env`

Docker 部署文件在 `docker/` 目录，进入后复制示例配置（后续命令都在该目录执行）：

```bash
cd docker
cp .env.example .env
# 编辑 .env，至少填一个 LLM API Key
```

最少要改的两行（挑你有的供应商）：

```env
DASHSCOPE_API_KEY=sk-xxx     # 通义千问
DEEPSEEK_API_KEY=sk-xxx      # DeepSeek
ZAI_API_KEY=xxx              # 智谱 GLM
QIANFAN_API_KEY=xxx          # 千帆
```

如果 Wikipedia / DuckDuckGo 在你环境连不上，可选地追加：

```env
# 给网络类工具开代理（默认全部直连；只对白名单里的 tool 临时切代理）
TOOL_HTTP_PROXY=http://127.0.0.1:10809
TOOL_PROXY_WHITELIST=wikipedia,duckduckgo_results_json
```

> 容器内的 `127.0.0.1` 指向容器自己。要走宿主机的代理，请用
> `host.docker.internal:10809`（Docker Desktop / Docker Engine ≥ 20.10），
> 或把代理容器加入同一个 compose 网络。详细机制见
> [study_ai_agent/README.md - 网络类工具代理](../study_ai_agent/README.md#网络类工具代理)。

### 3.2 启动

```bash
docker compose build
docker compose up -d
```

### 3.3 验证

```bash
# 容器状态
docker compose ps

# 后端日志（看 API Key 是否被识别）
docker compose logs -f backend
# 预期看到：DASHSCOPE API key configured, available  / DeepSeek API key ...

# 前端日志
docker compose logs -f frontend

# 浏览器打开
#   前端：http://localhost:3000
#   后端健康检查：curl http://localhost:8000/health
#   后端 skill 列表：curl http://localhost:8000/skeletons | jq
```

### 3.4 停止

```bash
docker compose down            # 停止并删容器
docker compose down -v         # 顺带清掉挂载的 logs volume
```

## 4. 单独构建（不通过 compose）

在 `docker/` 目录内执行（构建上下文为仓库根 `..`）：

### 后端

```bash
cd docker
docker build -t study-ai-agent-backend -f Dockerfile.backend ..

docker run --rm -p 8000:8000 \
  --env-file .env \
  -v "$(pwd)/../logs/backend:/app/logs" \
  --name study-backend \
  study-ai-agent-backend
```

### 前端

```bash
docker build \
  --build-arg VITE_API_BASE_URL=http://localhost:8000 \
  -t study-ai-agent-frontend -f Dockerfile.frontend ..

docker run --rm -p 3000:80 \
  -e BACKEND_UPSTREAM=http://host.docker.internal:8000 \
  --name study-frontend \
  study-ai-agent-frontend
```

> `host.docker.internal` 让容器访问宿主机上的后端（仅在 Docker Desktop / Docker for Mac / Windows 上默认开启；
> Linux 需加 `--add-host=host.docker.internal:host-gateway`）。

## 5. 镜像细节

### 5.1 后端多阶段

```
python:3.11-slim
  ├─ builder: 装 build-essential / pip install -r requirements.txt / pip install -e .
  └─ runtime: 只复制 /install + 源码，非 root 运行，HEALTHCHECK 打 /health
```

要点：

- **`/install` 路径**：所有 pip 包装到 `/install`，runtime 阶段直接 `COPY --from=builder /install /install`，镜像里没有 pip 缓存。
- **单 worker**：`WORKERS=1`。SSE 长连接是异步的，多 worker 需要 sticky session，学习项目没必要。
- **非 root**：`USER app`，降低容器逃逸风险。
- **HEALTHCHECK**：每 30s 探 `/health`，编排层可据此决定重启。

### 5.2 前端多阶段

```
node:20-alpine
  └─ builder: npm ci → npm run build（Vite 注入 VITE_*）
nginx:1.27-alpine
  └─ runtime: 复制 dist/ + nginx 模板 + entrypoint
```

要点：

- **`/api` 反代** + **POST `/` SSE 反代**：浏览器 → nginx → 后端，单域名部署。
- **SSE 友好**：`proxy_buffering off; proxy_read_timeout 86400s;`，避免流被截断。
- **`envsubst` 渲染**：`BACKEND_UPSTREAM` 在容器启动时由 `docker-entrypoint.sh` 注入。
- **gzip + 长缓存**：`/assets/` 走 immutable 缓存一年。

## 6. 常见问题

| 现象 | 原因 / 处理 |
| --- | --- |
| 后端起不来：`No available model providers!` | `.env` 没填任何 LLM API Key。填一个再 `docker compose up -d backend` |
| 浏览器打开 `:3000` 后 skill 列表是空的 | ① 浏览器访问后端的网络问题（确认后端 8000 已暴露）；② `/config` 页调整 `VITE_API_BASE_URL` |
| SSE 流被截断（`ERR_INCOMPLETE_CHUNKED_ENCODING`） | 走 nginx 反代时没禁 buffering。已用本仓库的 `nginx.conf`，若是自己改的请保留 `proxy_buffering off` |
| 修改后端代码后看不到效果 | 镜像需要重新构建：`docker compose build backend && docker compose up -d backend` |
| 修改前端代码 | 重新构建前端镜像：`docker compose build frontend && docker compose up -d frontend` |
| `host.docker.internal` 在 Linux 不识别 | 启动命令加 `--add-host=host.docker.internal:host-gateway`，或直接用宿主机 IP |
| 镜像体积太大 | builder 阶段已剔除缓存；如还嫌大可用 `dive` 进一步审计；考虑换 `python:3.11-alpine`（但生态兼容性更差） |

## 7. 生产化建议（学习项目之外）

- **持久化 checkpointer**：把 `InMemorySaver` 换成 Postgres / SQLite + `langgraph-checkpoint-postgres`
- **HTTPS**：前端前面加一层 Caddy / Traefik 自动签发证书
- **镜像仓库**：推送到 ghcr.io / Docker Hub，给镜像打 `git sha` tag
- **CI**：用 `docker buildx` 跨平台构建；缓存推送到 registry
- **可观测性**：接 OpenTelemetry，后端 / 前端都打 trace
- **限流 / 鉴权**：nginx 层加 basic auth 或 JWT，前端登录态

## 8. 命令速查

```bash
# 构建
docker compose build
docker compose build --no-cache            # 强制全量重建
docker compose build backend               # 只构建后端

# 启停
docker compose up -d
docker compose down
docker compose restart backend

# 调试
docker compose ps
docker compose logs -f
docker compose logs -f --tail=200 backend
docker compose exec backend bash
docker compose exec backend python -c "import src.core.server; print('ok')"

# 资源占用
docker compose stats
```
