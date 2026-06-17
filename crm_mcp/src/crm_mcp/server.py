"""FastMCP 服务入口：注册所有工具、资源、Prompts。

启动
====
::

    # 装包后
    crm-mcp

    # 或开发态
    python -m crm_mcp

传输
----
默认 ``streamable_http``，监听 ``CRM_MCP_HOST:CRM_MCP_PORT``（默认 0.0.0.0:8001）。
"""
from __future__ import annotations

import json
import logging
import sys
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from crm_mcp.config import settings
from crm_mcp.formatters import render_overview_md
from crm_mcp.logging_setup import setup_logging
from crm_mcp.store import get_store
from crm_mcp.tools import (
    activities as activities_tools,
)
from crm_mcp.tools import (
    contacts as contacts_tools,
)
from crm_mcp.tools import (
    customers as customer_tools,
)
from crm_mcp.tools import (
    leads as leads_tools,
)
from crm_mcp.tools import (
    opportunities as opportunities_tools,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 生命周期：启动加载数据，关闭 flush
# ---------------------------------------------------------------------------
@asynccontextmanager
async def _lifespan(server: Any) -> AsyncIterator[dict[str, Any]]:
    store = get_store()
    await store.setup()
    logger.info(
        "CRM MCP server ready: %s | data=%s",
        server.name if hasattr(server, "name") else "crm_mcp",
        settings.DATA_FILE,
    )
    try:
        yield {"store": store}
    finally:
        # 关闭前最后一次 flush，防内存里还有未写盘的变更
        await store.flush()
        logger.info("CRM MCP server stopped, data flushed")


# ---------------------------------------------------------------------------
# 服务构造
# ---------------------------------------------------------------------------
def build_server() -> Any:
    """构造并返回配置好的 FastMCP 实例。"""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as e:  # pragma: no cover - 缺包时早暴露
        raise SystemExit(
            "MCP SDK 未安装。请先 `pip install mcp`（建议 >=1.2）。"
        ) from e

    mcp = FastMCP(
        name="crm_mcp",
        instructions=(
            "CRM 系统 MCP 服务。提供客户 (Customer)、联系人 (Contact)、销售线索 (Lead)、"
            "商机 (Opportunity)、跟进活动 (Activity) 五个实体的 CRUD 工具集。"
            "数据保存在本地 JSON 文件中；所有工具的写操作都是同步落盘。"
            "默认返回 Markdown 格式便于阅读；可在 response_format 参数中指定 'json'。"
        ),
        lifespan=_lifespan,
        host=settings.HOST,
        port=settings.PORT,
    )

    # 工具
    customer_tools.register(mcp)
    contacts_tools.register(mcp)
    leads_tools.register(mcp)
    opportunities_tools.register(mcp)
    activities_tools.register(mcp)

    # 资源 & prompts
    _register_resources(mcp)
    _register_prompts(mcp)

    return mcp


# ---------------------------------------------------------------------------
# 资源（read-only 数据视图）
# ---------------------------------------------------------------------------
def _register_resources(mcp: Any) -> None:
    @mcp.resource("crm://overview")
    async def crm_overview() -> str:
        """CRM 整体数据概览（统计 + 分布）。"""
        store = get_store()
        stats = store.overview()
        return render_overview_md(stats)

    @mcp.resource("crm://data-file")
    async def crm_data_file_info() -> str:
        """当前生效的数据文件路径（仅元信息，不暴露内容）。"""
        info = {
            "data_file": str(settings.DATA_FILE),
            "seed_file": str(settings.SEED_FILE),
        }
        return json.dumps(info, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Prompts（给 LLM 的"工作流模板"）
# ---------------------------------------------------------------------------
def _register_prompts(mcp: Any) -> None:
    @mcp.prompt("weekly_pipeline_review")
    async def weekly_pipeline_review() -> str:
        """每周管线复盘：用 MCP 工具拉数据并给出结构化总结。"""
        return (
            "请基于 CRM 数据做一次本周管线复盘：\n"
            "1. 调用 crm_list_opportunities 拉所有 open 阶段商机；\n"
            "2. 调用 crm_list_activities 拉本周完成的活动；\n"
            "3. 对比上周的管线价值变化（说明活动推动效果）；\n"
            "4. 给出 TOP 3 高优先级跟进建议（owner / next action / 风险点）。"
        )

    @mcp.prompt("lead_to_deal_workflow")
    async def lead_to_deal_workflow() -> str:
        """线索 -> 商机 转化工作流模板。"""
        return (
            "请按以下步骤处理合格线索：\n"
            "1. 使用 crm_list_leads 找到 status='qualified' 的线索；\n"
            "2. 对每条线索读取详情 (crm_get_lead)；\n"
            "3. 确认联系人邮箱可达，调用 crm_convert_lead 生成客户+联系人；\n"
            "4. 立即调用 crm_create_opportunity 创建初始商机（stage=discovery）；\n"
            "5. 安排首次跟进活动 (crm_create_activity)。"
        )


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def main() -> None:
    """CLI 入口：``crm-mcp`` 命令。"""
    setup_logging(settings.LOG_LEVEL)
    mcp = build_server()
    # FastMCP 的 run() 默认 stdio；这里强制 streamable_http 以便远程访问。
    try:
        mcp.run(transport="streamable-http")
    except KeyboardInterrupt:  # pragma: no cover
        logger.info("interrupted, shutting down")
        sys.exit(0)


if __name__ == "__main__":
    main()
