# ==================== 后端 Dockerfile ====================
# 多阶段构建：
#   builder   - 装完整依赖（含 dev 工具）跑 ruff/pytest
#   runtime   - 只装运行时依赖，体积更小
#
# 构建：
#   docker build -t study-ai-agent-backend -f study_ai_agent/Dockerfile study_ai_agent
# 运行：
#   docker run --rm -p 8000:8000 --env-file .env.production study-ai-agent-backend
# =================================================================
# ---- builder 阶段：装所有依赖（含 dev），可在此阶段跑 lint/测试 ----
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

# 仅在 builder 装编译工具，runtime 阶段不再需要
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1) 先 copy 锁文件，最大化层缓存命中
COPY requirements.txt pyproject.toml ./
COPY config ./config

# 2) 装运行时 + dev 依赖到 /install 目录（runtime 阶段会复制过去）
RUN pip install --upgrade pip \
    && pip install --prefix=/install -r requirements.txt \
    && pip install --prefix=/install -e .

# 3) 跑一次 import 校验，确保包结构 / 关键依赖在镜像里能用
RUN python -c "import src.core.server; print('ok: import src.core.server')"

# ---- runtime 阶段：只保留运行时必需的东西 ----
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/install/bin:${PATH}" \
    PYTHONPATH="/install/lib/python3.11/site-packages:${PYTHONPATH}" \
    ENV=production \
    HOST=0.0.0.0 \
    PORT=8000 \
    WORKERS=1 \
    LOG_LEVEL=INFO

# 容器内用非 root 用户跑
RUN groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin app

# 从 builder 复制已装好的包
COPY --from=builder /install /install
# 复制项目源码
COPY --chown=app:app src ./src
COPY --chown=app:app cli ./cli
COPY --chown=app:app config ./config
COPY --chown=app:app main.py pyproject.toml ./

# 切到非 root
USER app
WORKDIR /app

EXPOSE 8000

# 健康检查（容器编排可选用）
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, sys; \
        sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)"

# 单 worker：SSE 长连接是异步的，多 worker 需要 sticky session；学习项目不开多 worker
CMD ["sh", "-c", "uvicorn src.core.server:app --host 0.0.0.0 --port 8000 --workers ${WORKERS} --log-level ${LOG_LEVEL,,}"]
