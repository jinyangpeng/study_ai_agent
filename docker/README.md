# Docker 部署

本目录集中存放 Study AI Agent 的全部 Docker 部署文件。构建上下文统一为**仓库根**，
由根目录的 `.dockerignore` 负责裁剪，避免把 venv / node_modules 等本地产物打进镜像。

## 文件清单

| 文件 | 角色 |
| --- | --- |
| `docker-compose.yml` | 一键编排：backend + frontend + 共享网络 |
| `.env.example` → `.env` | compose 启动期注入的环境变量（端口 / API Key / Vite 构建变量） |
| `Dockerfile.backend` | 后端多阶段镜像（deps + runtime） |
| `Dockerfile.frontend` | 前端多阶段镜像（node:20-alpine 构建 + nginx:alpine 托管） |
| `nginx.conf` | nginx 模板：SPA fallback + `/api` 反代 + SSE 友好 |
| `docker-entrypoint.sh` | 渲染 nginx 模板并启动 nginx |

> 根目录的 `.dockerignore` 不在本目录内——它必须放在构建上下文根（仓库根）才会生效。

## 快速启动

```bash
cd docker
cp .env.example .env          # 编辑 .env，至少填一个 LLM API Key
docker compose build
docker compose up -d
```

验证：

```bash
docker compose ps                       # 容器状态
docker compose logs -f backend          # 后端日志
curl http://localhost:8000/health       # 后端健康检查
# 前端：http://localhost:3000
```

停止：

```bash
docker compose down            # 停止并删容器
docker compose down -v         # 顺带清掉挂载的 logs volume
```

## 单独构建（不通过 compose）

```bash
cd docker

# 后端
docker build -t study-ai-agent-backend -f Dockerfile.backend ..
docker run --rm -p 8000:8000 \
  --env-file .env \
  -v "$(pwd)/../logs/backend:/app/logs" \
  --name study-backend \
  study-ai-agent-backend

# 前端
docker build \
  --build-arg VITE_API_BASE_URL=http://localhost:8000 \
  -t study-ai-agent-frontend -f Dockerfile.frontend ..
docker run --rm -p 3000:80 \
  -e BACKEND_UPSTREAM=http://host.docker.internal:8000 \
  --name study-frontend \
  study-ai-agent-frontend
```

> 也可以在仓库根用 `-f` 指定 compose 文件：`docker compose -f docker/docker-compose.yml up -d`。

更详细的镜像细节、调优、生产化建议见 [`../docs/DOCKER.md`](../docs/DOCKER.md)。
