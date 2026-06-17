"""CRM 数据模型 - 五个核心实体 + 输入/输出契约。

设计原则：
1. **存储模型与 API 模型分离** —— ``*Entity`` 包含 id / created_at / updated_at，
   写入磁盘时序列化；``*Create`` / ``*Update`` 是入参，强制 required / optional 边界。
2. **Pydantic v2** —— ``model_config = ConfigDict(...)`` + ``field_validator``。
3. **ID 自管理** —— 不接外部发号器，由 store 统一生成 ``C-{n}`` / ``CO-{n}`` 前缀。
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from crm_mcp.enums import (
    ActivityStatus,
    ActivityType,
    ContactRole,
    CustomerStatus,
    CustomerTier,
    Industry,
    LeadSource,
    LeadStatus,
    OpportunityStage,
    Priority,
)

# Pydantic 的 EmailStr 要求 email-validator；为了保持依赖最小，
# 这里用普通 str + 自定义 validator。
EmailStrCompat = Annotated[str, Field(pattern=r"^[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}$")]


# ---------------------------------------------------------------------------
# 通用 mixin：所有实体都有这些字段
# ---------------------------------------------------------------------------
class _AuditMixin(BaseModel):
    """统一的审计字段。"""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="实体唯一 ID（由 store 生成）")
    created_at: datetime = Field(..., description="创建时间（ISO 8601）")
    updated_at: datetime = Field(..., description="最后修改时间（ISO 8601）")
    owner: Optional[str] = Field(default=None, description="负责人（销售名）")


# ---------------------------------------------------------------------------
# 客户 (Customer)
# ---------------------------------------------------------------------------
class CustomerCreate(BaseModel):
    """创建客户输入。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    name: str = Field(..., min_length=1, max_length=100, description="客户名称")
    industry: Industry = Field(default=Industry.OTHER, description="所属行业")
    tier: CustomerTier = Field(default=CustomerTier.STANDARD, description="客户分级")
    status: CustomerStatus = Field(default=CustomerStatus.PROSPECT, description="客户状态")
    website: Optional[str] = Field(default=None, max_length=200, description="官网")
    phone: Optional[str] = Field(default=None, max_length=40, description="总机电话")
    address: Optional[str] = Field(default=None, max_length=200, description="办公地址")
    annual_revenue: Optional[float] = Field(default=None, ge=0, description="客户年收入（元）")
    employee_count: Optional[int] = Field(default=None, ge=0, description="员工人数")
    notes: Optional[str] = Field(default=None, max_length=2000, description="备注")
    owner: Optional[str] = Field(default=None, max_length=50, description="负责人")

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name cannot be blank")
        return v.strip()


class CustomerUpdate(BaseModel):
    """更新客户输入（所有字段可选）。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    industry: Optional[Industry] = None
    tier: Optional[CustomerTier] = None
    status: Optional[CustomerStatus] = None
    website: Optional[str] = Field(default=None, max_length=200)
    phone: Optional[str] = Field(default=None, max_length=40)
    address: Optional[str] = Field(default=None, max_length=200)
    annual_revenue: Optional[float] = Field(default=None, ge=0)
    employee_count: Optional[int] = Field(default=None, ge=0)
    notes: Optional[str] = Field(default=None, max_length=2000)
    owner: Optional[str] = Field(default=None, max_length=50)


class Customer(_AuditMixin):
    """客户实体（持久化形态）。"""

    name: str
    industry: Industry
    tier: CustomerTier
    status: CustomerStatus
    website: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    annual_revenue: Optional[float] = None
    employee_count: Optional[int] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# 联系人 (Contact)
# ---------------------------------------------------------------------------
class ContactCreate(BaseModel):
    """创建联系人输入。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    customer_id: str = Field(..., min_length=1, max_length=20, description="所属客户 ID")
    full_name: str = Field(..., min_length=1, max_length=50, description="联系人姓名")
    title: Optional[str] = Field(default=None, max_length=80, description="职位")
    role: ContactRole = Field(default=ContactRole.OTHER, description="角色")
    email: Optional[EmailStrCompat] = None
    phone: Optional[str] = Field(default=None, max_length=40, description="手机/座机")
    linkedin: Optional[str] = Field(default=None, max_length=200, description="LinkedIn URL")
    is_primary: bool = Field(default=False, description="是否主要联系人")
    notes: Optional[str] = Field(default=None, max_length=2000, description="备注")
    owner: Optional[str] = Field(default=None, max_length=50)


class ContactUpdate(BaseModel):
    """更新联系人输入。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    customer_id: Optional[str] = Field(default=None, min_length=1, max_length=20)
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=50)
    title: Optional[str] = Field(default=None, max_length=80)
    role: Optional[ContactRole] = None
    email: Optional[EmailStrCompat] = None
    phone: Optional[str] = Field(default=None, max_length=40)
    linkedin: Optional[str] = Field(default=None, max_length=200)
    is_primary: Optional[bool] = None
    notes: Optional[str] = Field(default=None, max_length=2000)
    owner: Optional[str] = Field(default=None, max_length=50)


class Contact(_AuditMixin):
    """联系人实体。"""

    customer_id: str
    full_name: str
    title: Optional[str] = None
    role: ContactRole
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    is_primary: bool = False
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# 销售线索 (Lead)
# ---------------------------------------------------------------------------
class LeadCreate(BaseModel):
    """创建线索输入。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    contact_name: str = Field(..., min_length=1, max_length=50, description="联系人姓名")
    company: str = Field(..., min_length=1, max_length=100, description="公司名")
    email: Optional[EmailStrCompat] = None
    phone: Optional[str] = Field(default=None, max_length=40)
    title: Optional[str] = Field(default=None, max_length=80)
    source: LeadSource = Field(default=LeadSource.OTHER, description="线索来源")
    status: LeadStatus = Field(default=LeadStatus.NEW, description="线索状态")
    industry: Industry = Field(default=Industry.OTHER)
    estimated_value: Optional[float] = Field(default=None, ge=0, description="预估价值（元）")
    notes: Optional[str] = Field(default=None, max_length=2000)
    owner: Optional[str] = Field(default=None, max_length=50)


class LeadUpdate(BaseModel):
    """更新线索输入。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    contact_name: Optional[str] = Field(default=None, min_length=1, max_length=50)
    company: Optional[str] = Field(default=None, min_length=1, max_length=100)
    email: Optional[EmailStrCompat] = None
    phone: Optional[str] = Field(default=None, max_length=40)
    title: Optional[str] = Field(default=None, max_length=80)
    source: Optional[LeadSource] = None
    status: Optional[LeadStatus] = None
    industry: Optional[Industry] = None
    estimated_value: Optional[float] = Field(default=None, ge=0)
    notes: Optional[str] = Field(default=None, max_length=2000)
    owner: Optional[str] = Field(default=None, max_length=50)


class Lead(_AuditMixin):
    """销售线索实体。"""

    contact_name: str
    company: str
    email: Optional[str] = None
    phone: Optional[str] = None
    title: Optional[str] = None
    source: LeadSource
    status: LeadStatus
    industry: Industry
    estimated_value: Optional[float] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# 商机 (Opportunity)
# ---------------------------------------------------------------------------
class OpportunityCreate(BaseModel):
    """创建商机输入。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    name: str = Field(..., min_length=1, max_length=120, description="商机名（如年度采购）")
    customer_id: str = Field(..., min_length=1, max_length=20, description="所属客户 ID")
    primary_contact_id: Optional[str] = Field(default=None, max_length=20, description="主要联系人 ID")
    stage: OpportunityStage = Field(default=OpportunityStage.DISCOVERY)
    amount: float = Field(default=0.0, ge=0, description="商机金额（元）")
    currency: str = Field(default="CNY", min_length=3, max_length=3, description="货币代码（ISO 4217）")
    probability: int = Field(
        default=10, ge=0, le=100, description="赢率百分比（0-100）"
    )
    priority: Priority = Field(default=Priority.MEDIUM)
    expected_close_date: Optional[datetime] = Field(default=None, description="预计成交日期")
    description: Optional[str] = Field(default=None, max_length=2000)
    owner: Optional[str] = Field(default=None, max_length=50)


class OpportunityUpdate(BaseModel):
    """更新商机输入。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    customer_id: Optional[str] = Field(default=None, min_length=1, max_length=20)
    primary_contact_id: Optional[str] = Field(default=None, max_length=20)
    stage: Optional[OpportunityStage] = None
    amount: Optional[float] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    probability: Optional[int] = Field(default=None, ge=0, le=100)
    priority: Optional[Priority] = None
    expected_close_date: Optional[datetime] = None
    description: Optional[str] = Field(default=None, max_length=2000)
    owner: Optional[str] = Field(default=None, max_length=50)


class Opportunity(_AuditMixin):
    """商机实体。"""

    name: str
    customer_id: str
    primary_contact_id: Optional[str] = None
    stage: OpportunityStage
    amount: float
    currency: str
    probability: int
    priority: Priority
    expected_close_date: Optional[datetime] = None
    description: Optional[str] = None


# ---------------------------------------------------------------------------
# 跟进活动 (Activity)
# ---------------------------------------------------------------------------
class ActivityCreate(BaseModel):
    """创建跟进活动输入。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    activity_type: ActivityType = Field(default=ActivityType.NOTE)
    subject: str = Field(..., min_length=1, max_length=120, description="活动主题")
    description: Optional[str] = Field(default=None, max_length=4000, description="详细描述/纪要")
    status: ActivityStatus = Field(default=ActivityStatus.PLANNED)
    customer_id: Optional[str] = Field(default=None, max_length=20)
    contact_id: Optional[str] = Field(default=None, max_length=20)
    lead_id: Optional[str] = Field(default=None, max_length=20)
    opportunity_id: Optional[str] = Field(default=None, max_length=20)
    due_at: Optional[datetime] = Field(default=None, description="截止时间")
    completed_at: Optional[datetime] = Field(default=None, description="实际完成时间")
    owner: Optional[str] = Field(default=None, max_length=50)

    @field_validator("subject")
    @classmethod
    def _subject_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("subject cannot be blank")
        return v.strip()


class ActivityUpdate(BaseModel):
    """更新活动输入。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    activity_type: Optional[ActivityType] = None
    subject: Optional[str] = Field(default=None, min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=4000)
    status: Optional[ActivityStatus] = None
    customer_id: Optional[str] = Field(default=None, max_length=20)
    contact_id: Optional[str] = Field(default=None, max_length=20)
    lead_id: Optional[str] = Field(default=None, max_length=20)
    opportunity_id: Optional[str] = Field(default=None, max_length=20)
    due_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    owner: Optional[str] = Field(default=None, max_length=50)


class Activity(_AuditMixin):
    """跟进活动实体。"""

    activity_type: ActivityType
    subject: str
    description: Optional[str] = None
    status: ActivityStatus
    customer_id: Optional[str] = None
    contact_id: Optional[str] = None
    lead_id: Optional[str] = None
    opportunity_id: Optional[str] = None
    due_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# 列表查询的通用入参（paging + 关键字）
# ---------------------------------------------------------------------------
class ListQuery(BaseModel):
    """通用列表查询入参：分页 + 关键字 + 排序。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    query: Optional[str] = Field(default=None, max_length=100, description="关键字（按名称/主题模糊匹配）")
    limit: Optional[int] = Field(default=None, ge=1, le=100, description="分页大小")
    offset: Optional[int] = Field(default=0, ge=0, description="分页偏移")
    sort_by: Optional[str] = Field(
        default=None, max_length=30, description="排序字段（如 created_at / updated_at / name）"
    )
    sort_order: Optional[str] = Field(
        default="desc", pattern="^(asc|desc)$", description="排序方向"
    )


__all__ = [
    "CustomerCreate",
    "CustomerUpdate",
    "Customer",
    "ContactCreate",
    "ContactUpdate",
    "Contact",
    "LeadCreate",
    "LeadUpdate",
    "Lead",
    "OpportunityCreate",
    "OpportunityUpdate",
    "Opportunity",
    "ActivityCreate",
    "ActivityUpdate",
    "Activity",
    "ListQuery",
]
