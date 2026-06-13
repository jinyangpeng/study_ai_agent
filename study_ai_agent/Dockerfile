# ==================== 后端 Dockerfile ====================
# 多阶段构建：
#   deps    - 装依赖到 /install（apt + pip 都用 BuildKit 缓存挂载，加速重建）
#   runtime - 只保留运行时必需的东西（无编译器、无 dev 依赖，体积小）
#
# 构建（需要 BuildKit，Docker Desktop 默认开启）：
#   docker build -t study-ai-agent-backend -f study_ai_agent/Dockerfile study_ai_agent
# 运行：
#   docker run --rm -p 8000:8000 --env-file .env study-ai-agent-backend
# =================================================================
# syntax=docker/dockerfile:1.6
# ---- deps 阶段：装运行时 + 项目自身到 /install（runtime 会整体复制） ----
FROM python:3.11-slim AS deps

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 1) 编译工具（只为编译 C 扩展；runtime 不需要）
#    用 BuildKit cache mount 持久化 apt 缓存，重建时不再重下包
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# 2) 先 copy 锁文件，最大化层缓存命中
COPY requirements.txt pyproject.toml ./
COPY config ./config

# 3) 装运行时依赖到 /install；用 cache mount 持久化 pip 下载缓存
#    --no-deps: deps 已经在 -r requirements.txt 里装过，避免重复解析
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip \
    && pip install --prefix=/install -r requirements.txt \
    && pip install --prefix=/install --no-deps -e .

# ---- runtime 阶段：只保留运行时必需的东西 ----
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/install/bin:${PATH}" \
    PYTHONPATH="/install/lib/python3.11/site-packages:/app:${PYTHONPATH}" \
    ENV=production \
    HOST=0.0.0.0 \
    PORT=8000 \
    WORKERS=1 \
    LOG_LEVEL=INFO

# 容器内用非 root 用户跑
RUN groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin app

# 必须先设 WORKDIR，COPY 的 `./` 才是 /app
WORKDIR /app

# 从 deps 复制已装好的包
COPY --from=deps /install /install
# 复制项目源码（分开 COPY，避开 BuildKit 在 Windows 上的多源 COPY 边角问题）
COPY --chown=app:app src ./src
COPY --chown=app:app cli ./cli
COPY --chown=app:app config ./config
COPY --chown=app:app main.py pyproject.toml ./

# 切到非 root
USER app

EXPOSE 8000

# 健康检查（容器编排可选用）
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, sys; \
        sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)"

# 单 worker：SSE 长连接是异步的，多 worker 需要 sticky session；学习项目不开多 worker
# 用 POSIX `tr` 把 LOG_LEVEL 转为小写（兼容 dash，比 bash ${VAR,,} 通用）
CMD ["sh", "-c", "exec uvicorn src.core.server:app --host 0.0.0.0 --port 8000 --workers ${WORKERS} --log-level $(printf '%s' \"$LOG_LEVEL\" | tr '[:upper:]' '[:lower:]')"]
