# CRM MCP Service - Makefile
#
# 用法：
#   make help        - 显示帮助
#   make install     - 安装当前包（editable）
#   make run         - 启动服务（streamable_http，端口 8001）
#   make smoke       - 跑冒烟测试
#   make lint        - ruff check
#   make fmt         - ruff format
#   make clean       - 清理 __pycache__ + 临时数据

PY ?= python
PORT ?= 8001

.PHONY: help
help:
	@echo "CRM MCP Service - make targets:"
	@echo "  install   - pip install -e ."
	@echo "  run       - start FastMCP server (streamable_http, port $(PORT))"
	@echo "  smoke     - run smoke test"
	@echo "  lint      - ruff check"
	@echo "  fmt       - ruff format"
	@echo "  clean     - remove caches + runtime data file"

.PHONY: install
install:
	$(PY) -m pip install -e .

.PHONY: run
run:
	CRM_MCP_PORT=$(PORT) $(PY) -m crm_mcp

.PHONY: smoke
smoke:
	$(PY) tests/smoke.py

.PHONY: lint
lint:
	$(PY) -m ruff check src tests

.PHONY: fmt
fmt:
	$(PY) -m ruff format src tests

.PHONY: clean
clean:
	rm -rf src/crm_mcp/__pycache__ src/crm_mcp/tools/__pycache__ tests/__pycache__
	rm -f data/crm_store.json data/crm_store.json.tmp
