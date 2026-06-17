"""JSON 文件持久化层。

设计要点
========
1. **全内存 cache + 异步锁**：启动时一次性把 JSON 加载到内存；后续读写都在内存中
   进行，由 :class:`asyncio.Lock` 串行化写操作；写完再 ``fsync`` 落盘。
2. **原子写**：先写到 ``<file>.tmp``，再 ``os.replace`` —— 避免进程被强杀时
   把数据文件写到一半。
3. **ID 自增**：每个实体一个独立计数器（``seq``），前缀分别 ``C`` / ``CT`` /
   ``L`` / ``O`` / ``A``，与 seed 里的 ID 不冲突。
4. **冷启动**：第一次 ``setup()`` 时如果 ``DATA_FILE`` 不存在，从 ``SEED_FILE`` 拷贝。
5. **schema 校验**：每次启动都把数据按 Pydantic 模型重读一遍，尽早暴露脏数据。
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from crm_mcp.config import settings
from crm_mcp.errors import NotFoundError, StorageError, ValidationError
from crm_mcp.models import (
    Activity,
    Contact,
    Customer,
    Lead,
    Opportunity,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def _now() -> datetime:
    """统一的 UTC 时间戳（带 tzinfo）。"""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# 集合注册表：每个实体类型一个 collection
# ---------------------------------------------------------------------------
class _Collection(Generic[T]):
    """单实体的内存集合 + 文件持久化。

    写操作由外层 :class:`CRMStore` 的锁串行化；本类不持锁。
    """

    def __init__(self, name: str, model_cls: type[T], id_prefix: str) -> None:
        self.name = name
        self.model_cls = model_cls
        self.id_prefix = id_prefix
        self._items: dict[str, T] = {}
        self._seq: int = 0

    # ---- 序列化 ----
    def to_dict(self) -> dict[str, Any]:
        return {
            "_seq": self._seq,
            "items": {k: v.model_dump(mode="json") for k, v in self._items.items()},
        }

    def load_dict(self, payload: dict[str, Any]) -> None:
        self._seq = int(payload.get("_seq", 0))
        raw_items = payload.get("items", {}) or {}
        # 严格按 Pydantic 模型重读，尽早暴露脏数据
        items: dict[str, T] = {}
        for k, v in raw_items.items():
            try:
                items[str(k)] = self.model_cls.model_validate(v)
            except Exception as e:  # noqa: BLE001
                raise StorageError(
                    f"Invalid {self.name} record '{k}': {e}",
                    hint="Delete the JSON file or fix the record manually",
                ) from e
        self._items = items

    # ---- ID ----
    def next_id(self) -> str:
        self._seq += 1
        return f"{self.id_prefix}-{self._seq:06d}"

    # ---- CRUD ----
    def list(self) -> list[T]:
        return list(self._items.values())

    def get(self, item_id: str) -> T:
        try:
            return self._items[item_id]
        except KeyError as e:
            raise NotFoundError(
                f"{self.name} '{item_id}' not found",
                hint=f"Use crm_list_{self.name}s to see available IDs",
            ) from e

    def exists(self, item_id: str) -> bool:
        return item_id in self._items

    def add(self, item: T) -> T:
        if item.id in self._items:
            raise StorageError(
                f"{self.name} '{item.id}' already exists",
                hint="Use update instead of create",
            )
        self._items[item.id] = item
        return item

    def replace(self, item: T) -> T:
        if item.id not in self._items:
            raise NotFoundError(
                f"{self.name} '{item.id}' not found",
                hint="Use create instead of update",
            )
        self._items[item.id] = item
        return item

    def delete(self, item_id: str) -> None:
        if item_id not in self._items:
            raise NotFoundError(
                f"{self.name} '{item_id}' not found",
                hint="Check the ID and try again",
            )
        del self._items[item_id]

    def count(self) -> int:
        return len(self._items)


# ---------------------------------------------------------------------------
# 总 store
# ---------------------------------------------------------------------------
class CRMStore:
    """CRM 全局存储：5 个 collection + 异步锁 + 原子落盘。"""

    def __init__(self) -> None:
        self.customers = _Collection("customer", Customer, "C")
        self.contacts = _Collection("contact", Contact, "CT")
        self.leads = _Collection("lead", Lead, "L")
        self.opportunities = _Collection("opportunity", Opportunity, "O")
        self.activities = _Collection("activity", Activity, "A")
        self._lock = asyncio.Lock()
        self._loaded = False

    # ---- 生命周期 ----
    async def setup(self) -> None:
        """启动时调用：冷启动拷贝 seed → 加载数据 → 校验。"""
        if self._loaded:
            return
        async with self._lock:
            if self._loaded:
                return
            await asyncio.to_thread(self._load_sync)
            self._loaded = True
            logger.info(
                "CRMStore loaded: customers=%d contacts=%d leads=%d opportunities=%d activities=%d",
                self.customers.count(),
                self.contacts.count(),
                self.leads.count(),
                self.opportunities.count(),
                self.activities.count(),
            )

    def _load_sync(self) -> None:
        data_file: Path = settings.DATA_FILE
        seed_file: Path = settings.SEED_FILE

        data_file.parent.mkdir(parents=True, exist_ok=True)

        if not data_file.exists():
            if not seed_file.exists():
                raise StorageError(
                    f"Seed file not found: {seed_file}",
                    hint="Reinstall the package or check CRM_MCP_SEED_FILE",
                )
            data_file.write_text(seed_file.read_text(encoding="utf-8"), encoding="utf-8")
            logger.info("Initialized data file from seed: %s", data_file)

        try:
            raw = json.loads(data_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise StorageError(
                f"Data file is not valid JSON: {e}",
                hint=f"Delete {data_file} to reset from seed",
            ) from e

        try:
            self.customers.load_dict(raw.get("customers", {}))
            self.contacts.load_dict(raw.get("contacts", {}))
            self.leads.load_dict(raw.get("leads", {}))
            self.opportunities.load_dict(raw.get("opportunities", {}))
            self.activities.load_dict(raw.get("activities", {}))
        except StorageError:
            raise
        except Exception as e:  # noqa: BLE001
            raise StorageError(
                f"Failed to load CRM data: {e}",
                hint=f"Inspect {data_file} or delete to reset",
            ) from e

    async def flush(self) -> None:
        """强制把内存数据写回磁盘（原子写）。"""
        async with self._lock:
            await asyncio.to_thread(self._write_sync)

    def _write_sync(self) -> None:
        payload = {
            "version": 1,
            "saved_at": _now().isoformat(),
            "customers": self.customers.to_dict(),
            "contacts": self.contacts.to_dict(),
            "leads": self.leads.to_dict(),
            "opportunities": self.opportunities.to_dict(),
            "activities": self.activities.to_dict(),
        }
        data_file: Path = settings.DATA_FILE
        data_file.parent.mkdir(parents=True, exist_ok=True)

        # 写到同目录临时文件，再原子替换
        fd, tmp_path = tempfile.mkstemp(
            prefix=f".{data_file.name}.", suffix=".tmp", dir=str(data_file.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, data_file)
        except Exception:
            # 清理临时文件，避免残留
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    # ---- 事务包装 ----
    async def write_through(self, mutate) -> Any:
        """在持锁状态下修改内存，然后写盘。返回 ``mutate`` 的返回值。

        用法::

            new = await store.write_through(lambda: store.customers.add(item))

        """
        async with self._lock:
            result = mutate()
            self._write_sync()
            return result

    # ---- 跨表引用校验 ----
    def ensure_customer_exists(self, customer_id: str) -> None:
        if not self.customers.exists(customer_id):
            raise ValidationError(
                f"customer_id '{customer_id}' does not exist",
                hint="Create the customer first via crm_create_customer",
            )

    def ensure_contact_exists(self, contact_id: str) -> None:
        if not self.contacts.exists(contact_id):
            raise ValidationError(
                f"contact_id '{contact_id}' does not exist",
                hint="Create the contact first via crm_create_contact",
            )

    def ensure_lead_exists(self, lead_id: str) -> None:
        if not self.leads.exists(lead_id):
            raise ValidationError(
                f"lead_id '{lead_id}' does not exist",
                hint="Create the lead first via crm_create_lead",
            )

    def ensure_opportunity_exists(self, opportunity_id: str) -> None:
        if not self.opportunities.exists(opportunity_id):
            raise ValidationError(
                f"opportunity_id '{opportunity_id}' does not exist",
                hint="Create the opportunity first via crm_create_opportunity",
            )

    def ensure_activity_exists(self, activity_id: str) -> None:
        if not self.activities.exists(activity_id):
            raise ValidationError(
                f"activity_id '{activity_id}' does not exist",
                hint="Create the activity first via crm_create_activity",
            )

    # ---- 统计概览 ----
    def overview(self) -> dict[str, Any]:
        return {
            "customers": {
                "total": self.customers.count(),
                "by_status": _count_by(self.customers.list(), "status"),
                "by_tier": _count_by(self.customers.list(), "tier"),
            },
            "contacts": {
                "total": self.contacts.count(),
                "primary": sum(1 for c in self.contacts.list() if c.is_primary),
            },
            "leads": {
                "total": self.leads.count(),
                "by_status": _count_by(self.leads.list(), "status"),
            },
            "opportunities": {
                "total": self.opportunities.count(),
                "by_stage": _count_by(self.opportunities.list(), "stage"),
                "pipeline_value": round(
                    sum(
                        o.amount * (o.probability / 100.0)
                        for o in self.opportunities.list()
                        if getattr(o.stage, "value", o.stage) not in {"closed_won", "closed_lost"}
                    ),
                    2,
                ),
            },
            "activities": {
                "total": self.activities.count(),
                "by_status": _count_by(self.activities.list(), "status"),
                "by_type": _count_by(self.activities.list(), "activity_type"),
            },
        }


def _count_by(items: list[BaseModel], field: str) -> dict[str, int]:
    """按字段值统计计数。Enum 用 .value 作为 key，避免出现 'CustomerStatus.ACTIVE'。"""
    out: dict[str, int] = {}
    for it in items:
        raw = getattr(it, field, None)
        if raw is None:
            key = "unknown"
        elif hasattr(raw, "value"):
            key = str(raw.value)
        else:
            key = str(raw)
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


# ---------------------------------------------------------------------------
# 全局单例（FastMCP 工具都通过这个访问 store）
# ---------------------------------------------------------------------------
_store: CRMStore | None = None


def get_store() -> CRMStore:
    """获取全局 :class:`CRMStore` 单例。"""
    global _store
    if _store is None:
        _store = CRMStore()
    return _store


async def reset_store_for_tests(new_store: CRMStore | None = None) -> CRMStore:
    """测试辅助：重置全局 store。生产代码不应调用。"""
    global _store
    _store = new_store or CRMStore()
    await _store.setup()
    return _store


__all__ = [
    "CRMStore",
    "get_store",
    "reset_store_for_tests",
    "deepcopy",  # 方便工具层做不可变快照
]
