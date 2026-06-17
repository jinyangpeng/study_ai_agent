"""CRM 自定义异常。

所有异常都是 :class:`CRMError` 的子类，可以被统一的 error formatter
捕获并格式化为 actionable 错误消息。
"""
from __future__ import annotations


class CRMError(Exception):
    """CRM 业务异常基类。"""

    code: str = "CRM_ERROR"
    status_code: int = 400

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:  # pragma: no cover
        base = f"[{self.code}] {self.message}"
        return f"{base} (hint: {self.hint})" if self.hint else base


class NotFoundError(CRMError):
    """实体不存在。"""

    code = "CRM_NOT_FOUND"
    status_code = 404


class ValidationError(CRMError):
    """入参非法（Pydantic 兜不住的语义级校验）。"""

    code = "CRM_VALIDATION"
    status_code = 422


class ConflictError(CRMError):
    """冲突（如外键指向不存在的实体）。"""

    code = "CRM_CONFLICT"
    status_code = 409


class StorageError(CRMError):
    """存储读写失败。"""

    code = "CRM_STORAGE"
    status_code = 500


__all__ = [
    "CRMError",
    "NotFoundError",
    "ValidationError",
    "ConflictError",
    "StorageError",
]
