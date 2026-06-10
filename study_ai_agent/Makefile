# ==================== Python 项目 Makefile ====================
# 类似前端 package.json 的 scripts，但更强大
# 用法: make <命令>

# 变量
PYTHON := python
PIP := pip
VENV := .venv
ENV_DEV := development
ENV_PROD := production

# 判断操作系统
ifeq ($(OS),Windows_NT)
    VENV_PYTHON := $(VENV)\Scripts\python
    VENV_PIP := $(VENV)\Scripts\pip
    ACTIVATE := $(VENV)\Scripts\activate
else
    VENV_PYTHON := $(VENV)/bin/python
    VENV_PIP := $(VENV)/bin/pip
    ACTIVATE := source $(VENV)/bin/activate
endif

.PHONY: help init venv install dev prod lint fmt clean env-dev env-prod

# 默认命令：显示帮助
help:
	@echo "可用命令:"
	@echo "  make init      - 一键初始化项目（虚拟环境 + 依赖 + .env）"
	@echo "  make venv      - 创建虚拟环境"
	@echo "  make install   - 安装项目依赖"
	@echo "  make dev       - 以开发环境运行项目"
	@echo "  make prod      - 以生产环境运行项目"
	@echo "  make lint      - 代码检查（ruff）"
	@echo "  make fmt       - 代码格式化（ruff）"
	@echo "  make clean     - 清理缓存和临时文件"
	@echo "  make env-dev   - 创建开发环境 .env 文件"
	@echo "  make env-prod  - 创建生产环境 .env 文件"

# 一键初始化
init: venv install env-dev env-prod
	@echo ""
	@echo "=========================================="
	@echo "🎉 项目初始化完成！"
	@echo ""
	@echo "下一步:"
	@echo "  1. 填写 .env.development 中的 API Key"
	@echo "  2. make dev 启动项目"
	@echo "=========================================="

# 创建虚拟环境
venv:
	@if [ -d "$(VENV)" ]; then echo "⏭️  虚拟环境已存在"; else 		$(PYTHON) -m venv $(VENV) && echo "✅ 虚拟环境创建成功"; fi

# 安装依赖
install: venv
	$(VENV_PIP) install -e ".[dev]"

# 开发环境运行
dev:
	ENV=$(ENV_DEV) $(VENV_PYTHON) main.py

# 生产环境运行
prod:
	ENV=$(ENV_PROD) $(VENV_PYTHON) main.py

# 代码检查
lint:
	$(VENV_PYTHON) -m ruff check app/ main.py

# 代码格式化
fmt:
	$(VENV_PYTHON) -m ruff format app/ main.py

# 清理
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf dist/ build/ *.egg-info logs/ 2>/dev/null || true
	@echo "✅ 清理完成"

# 创建开发环境 .env
env-dev:
	@if [ ! -f .env.development ]; then 		cp .env.example .env.development 2>/dev/null || 		echo -e "ENV=development\n\nDASHSCOPE_API_KEY=\nDEEPSEEK_API_KEY=\n\nLOG_LEVEL=DEBUG" > .env.development; 		echo "✅ 已创建 .env.development，请填入 API Key"; 	else echo "⏭️  .env.development 已存在"; fi

# 创建生产环境 .env
env-prod:
	@if [ ! -f .env.production ]; then 		cp .env.example .env.production 2>/dev/null || 		echo -e "ENV=production\n\nDASHSCOPE_API_KEY=\nDEEPSEEK_API_KEY=\n\nLOG_LEVEL=INFO" > .env.production; 		echo "✅ 已创建 .env.production，请填入 API Key"; 	else echo "⏭️  .env.production 已存在"; fi
