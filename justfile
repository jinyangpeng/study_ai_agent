# ==================== Study AI Agent - 根 justfile（monorepo 编排器）====================
#
# 作为仓库统一入口，委托到各子项目（study_ai_agent / study_ai_agent_ui / crm_mcp）。
# 子项目仍保留各自的 justfile，本文件提供高层组合命令与跨项目流程。
#
# 常用命令:
#   just                    - 显示帮助
#   just install            - 全栈装依赖（后端 venv + 前端 node_modules）
#   just dev                - 并发启动后端 + 前端（Ctrl+C 同时停）
#   just build              - 全栈构建（前端 dist + 后端无需构建）
#   just lint               - 全栈 lint（ruff + eslint）
#   just test               - 全栈测试（pytest + 前端 build 校验）
#   just docker-up          - docker compose 一键起（需先准备 docker/.env）
#   just clean              - 清理所有子项目缓存与产物
#
# 单栈命令见各分组：just --list
# =====================================================================================

# 跨平台：Windows 上用 Git bash 执行 recipe（与子项目 justfile 一致）
set windows-shell := ["C:\\Program Files\\Git\\bin\\bash.exe", "-c"]

# ---- 子项目路径 ----
backend_dir  := "study_ai_agent"
frontend_dir := "study_ai_agent_ui"
crm_dir      := "crm_mcp"
docker_dir   := "docker"

# ---- 后端 venv python 路径（跨平台动态计算）----
backend_python := `python -c "import os; print(r'study_ai_agent/.venv/Scripts/python.exe' if os.name == 'nt' else 'study_ai_agent/.venv/bin/python', end='')"`
# ---- 前端包管理器：优先 pnpm，回退 npm（用 shell 检测避免依赖 set lists）----
frontend_pm := if "$(test -f {{frontend_dir}}/pnpm-lock.yaml && echo pnpm || echo npm)" == "pnpm" { "pnpm" } else { "npm" }

# 默认：显示帮助
default: help

# 显示帮助
help:
    @echo "Study AI Agent (monorepo) - just targets:"
    @echo ""
    @echo "全栈:"
    @echo "  install        - 全栈装依赖（后端 venv + 前端 node_modules）"
    @echo "  dev            - 并发启动后端 + 前端（Ctrl+C 同时停）"
    @echo "  build          - 全栈构建（前端 tsc + vite build）"
    @echo "  lint           - 全栈 lint（ruff + eslint）"
    @echo "  test           - 全栈测试（pytest + 前端 build 校验）"
    @echo "  clean          - 清理所有子项目缓存与产物"
    @echo ""
    @echo "后端 (委托 study_ai_agent/justfile):"
    @echo "  dev-backend    - 后端开发模式（ENV=development）"
    @echo "  prod-backend   - 后端生产模式"
    @echo "  lint-backend   - ruff check"
    @echo "  fmt-backend    - ruff format"
    @echo "  test-backend   - pytest"
    @echo "  env-dev        - 生成 study_ai_agent/.env.development"
    @echo "  env-prod       - 生成 study_ai_agent/.env.production"
    @echo ""
    @echo "前端 (直接调 {{frontend_pm}}):"
    @echo "  dev-frontend   - vite dev server (http://localhost:3000)"
    @echo "  build-frontend - tsc -b && vite build"
    @echo "  lint-frontend  - eslint ."
    @echo "  preview-frontend - vite preview（预览构建产物）"
    @echo ""
    @echo "Docker:"
    @echo "  docker-build   - docker compose build（在 docker/ 内）"
    @echo "  docker-up      - docker compose up -d"
    @echo "  docker-down    - docker compose down"
    @echo "  docker-logs    - docker compose logs -f"
    @echo ""
    @echo "CRM MCP (委托 crm_mcp/justfile):"
    @echo "  crm-install    - CRM 子项目装依赖"
    @echo "  crm-run        - 启动 CRM MCP 服务（:8001）"
    @echo "  crm-inspect    - 启动 MCP Inspector"
    @echo "  crm-smoke      - CRM 冒烟测试"

# ============================================================
# 全栈命令
# ============================================================

# 全栈装依赖（后端 venv + 前端 node_modules）
install: install-backend install-frontend
    @echo ""
    @echo "[ok] 全栈依赖安装完成。"
    @echo "next: just env-dev  填入 API Key 后  just dev"

# 并发启动后端 + 前端；Ctrl+C 同时停掉两个进程
dev:
    @echo "[dev] 启动后端 (http://localhost:8000) + 前端 (http://localhost:3000)，Ctrl+C 同时停..."
    @echo ""
    @(cd {{backend_dir}} && "{{backend_python}}" -c "import os, runpy; os.environ['ENV']='development'; runpy.run_path('main.py', run_name='__main__')") & \
    BACK_PID=$$!; \
    (cd {{frontend_dir}} && {{frontend_pm}} run dev) & \
    FRONT_PID=$$!; \
    trap 'kill $$BACK_PID $$FRONT_PID 2>/dev/null' EXIT INT; \
    wait

# 全栈构建（前端 tsc + vite build；后端 Python 无构建步骤）
build: build-frontend
    @echo "[ok] 全栈构建完成。前端产物: {{frontend_dir}}/dist/"

# 全栈 lint
lint: lint-backend lint-frontend
    @echo "[ok] 全栈 lint 通过。"

# 全栈测试（后端 pytest；前端用 build 做类型 + 编译校验，前端无单元测试框架）
test: test-backend build-frontend
    @echo "[ok] 全栈测试完成。"

# 清理所有子项目缓存与产物
clean: clean-backend clean-frontend
    @echo "[ok] 全栈清理完成。"

# ============================================================
# 后端（委托 study_ai_agent/justfile）
# ============================================================

install-backend:
    @cd {{backend_dir}} && just install

dev-backend:
    @cd {{backend_dir}} && just dev

prod-backend:
    @cd {{backend_dir}} && just prod

lint-backend:
    @cd {{backend_dir}} && just lint

fmt-backend:
    @cd {{backend_dir}} && just fmt

test-backend:
    @cd {{backend_dir}} && .venv/Scripts/python -m pytest || .venv/bin/python -m pytest

env-dev:
    @cd {{backend_dir}} && just env-dev

env-prod:
    @cd {{backend_dir}} && just env-prod

clean-backend:
    @cd {{backend_dir}} && just clean

# ============================================================
# 前端（直接调 {{frontend_pm}}）
# ============================================================

install-frontend:
    @cd {{frontend_dir}} && {{frontend_pm}} install

dev-frontend:
    @cd {{frontend_dir}} && {{frontend_pm}} run dev

build-frontend:
    @cd {{frontend_dir}} && {{frontend_pm}} run build

lint-frontend:
    @cd {{frontend_dir}} && {{frontend_pm}} run lint

preview-frontend:
    @cd {{frontend_dir}} && {{frontend_pm}} run preview

clean-frontend:
    @cd {{frontend_dir}} && rm -rf dist build node_modules/.vite *.tsbuildinfo 2>/dev/null; echo "[ok] 前端产物已清理"

# ============================================================
# Docker（在 docker/ 目录内执行）
# ============================================================

docker-build:
    @cd {{docker_dir}} && docker compose build

docker-up:
    @cd {{docker_dir}} && docker compose up -d

docker-down:
    @cd {{docker_dir}} && docker compose down

docker-logs:
    @cd {{docker_dir}} && docker compose logs -f

# ============================================================
# CRM MCP（委托 crm_mcp/justfile）
# ============================================================

crm-install:
    @cd {{crm_dir}} && just install

crm-run:
    @cd {{crm_dir}} && just run

crm-inspect:
    @cd {{crm_dir}} && just inspect

crm-smoke:
    @cd {{crm_dir}} && just smoke
