"""CRM 业务枚举。

集中维护所有状态、类型、优先级等离散值，避免在模型/工具里硬编码字符串。
"""
from __future__ import annotations

from enum import Enum


# ---------------------------------------------------------------------------
# 通用
# ---------------------------------------------------------------------------
class ResponseFormat(str, Enum):
    """工具响应格式：markdown 给人读，json 给程序处理。"""

    MARKDOWN = "markdown"
    JSON = "json"


# ---------------------------------------------------------------------------
# 客户 (Customer)
# ---------------------------------------------------------------------------
class CustomerStatus(str, Enum):
    """客户所处的生命周期阶段。"""

    PROSPECT = "prospect"          # 潜在客户
    ACTIVE = "active"              # 活跃合作
    DORMANT = "dormant"            # 沉默客户
    CHURNED = "churned"            # 已流失
    ARCHIVED = "archived"          # 归档（不再跟进）


class CustomerTier(str, Enum):
    """客户分级。"""

    STRATEGIC = "strategic"        # 战略客户
    KEY = "key"                    # 重点客户
    STANDARD = "standard"          # 标准客户
    LONG_TAIL = "long_tail"        # 长尾客户


class Industry(str, Enum):
    """行业（典型枚举，避免自由文本导致数据脏）。"""

    INTERNET = "internet"
    FINANCE = "finance"
    MANUFACTURING = "manufacturing"
    RETAIL = "retail"
    EDUCATION = "education"
    HEALTHCARE = "healthcare"
    GOVERNMENT = "government"
    LOGISTICS = "logistics"
    ENERGY = "energy"
    OTHER = "other"


# ---------------------------------------------------------------------------
# 联系人 (Contact)
# ---------------------------------------------------------------------------
class ContactRole(str, Enum):
    """联系人在客户组织中的角色。"""

    DECISION_MAKER = "decision_maker"      # 决策人
    CHAMPION = "champion"                  # 内部支持者
    INFLUENCER = "influencer"              # 影响者
    USER = "user"                          # 最终用户
    GATEKEEPER = "gatekeeper"              # 门卫/助理
    OTHER = "other"


# ---------------------------------------------------------------------------
# 销售线索 (Lead)
# ---------------------------------------------------------------------------
class LeadStatus(str, Enum):
    """线索生命周期。"""

    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    UNQUALIFIED = "unqualified"
    CONVERTED = "converted"
    LOST = "lost"


class LeadSource(str, Enum):
    """线索来源渠道。"""

    WEBSITE = "website"
    REFERRAL = "referral"
    COLD_OUTREACH = "cold_outreach"
    EVENT = "event"
    ADVERTISEMENT = "advertisement"
    PARTNER = "partner"
    OTHER = "other"


# ---------------------------------------------------------------------------
# 商机 (Opportunity)
# ---------------------------------------------------------------------------
class OpportunityStage(str, Enum):
    """商机销售阶段。"""

    DISCOVERY = "discovery"
    QUALIFICATION = "qualification"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"


class Priority(str, Enum):
    """优先级。"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


# ---------------------------------------------------------------------------
# 跟进活动 (Activity)
# ---------------------------------------------------------------------------
class ActivityType(str, Enum):
    """活动类型。"""

    CALL = "call"
    EMAIL = "email"
    MEETING = "meeting"
    TASK = "task"
    NOTE = "note"
    DEMO = "demo"


class ActivityStatus(str, Enum):
    """活动状态。"""

    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


__all__ = [
    "ResponseFormat",
    "CustomerStatus",
    "CustomerTier",
    "Industry",
    "ContactRole",
    "LeadStatus",
    "LeadSource",
    "OpportunityStage",
    "Priority",
    "ActivityType",
    "ActivityStatus",
]
