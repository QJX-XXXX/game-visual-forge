from __future__ import annotations

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    USER_SELECTION_REQUIRED = "user_selection_required"
    CONFIRMATION_REQUIRED = "confirmation_required"
    CONFIRMATION_STALE = "confirmation_stale"
    DEPENDENCY_MISSING = "dependency_missing"
    IMAGE_UNREADABLE = "image_unreadable"
    IMAGE_CHANGED = "image_changed"
    INVALID_GRID = "invalid_grid"
    INVALID_FRAME = "invalid_frame"
    BACKGROUND_REMOVAL_UNAVAILABLE = "background_removal_unavailable"
    QUALITY_FAILED = "quality_failed"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    SUBMISSION_UNKNOWN = "submission_unknown"


class ForgeError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        recoverable: bool,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.recoverable = recoverable
        self.context = dict(context or {})

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "error": {
                "code": self.code.value,
                "message": self.message,
                "recoverable": self.recoverable,
                "context": self.context,
            },
        }
