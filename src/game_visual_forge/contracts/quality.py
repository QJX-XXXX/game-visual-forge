from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class QualityStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    NEEDS_ATTENTION = "needs_attention"
    NEEDS_VISUAL_REVIEW = "needs_visual_review"


@dataclass(frozen=True)
class QualityCheck:
    check_id: str
    status: QualityStatus
    message: str
    artifact_paths: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "status": self.status.value,
            "message": self.message,
            "artifact_paths": list(self.artifact_paths),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "QualityCheck":
        paths = value["artifact_paths"]
        if not isinstance(paths, list) or not all(isinstance(item, str) for item in paths):
            raise TypeError("artifact_paths must be a JSON array of strings")
        return cls(value["check_id"], QualityStatus(value["status"]), value["message"], tuple(paths))


@dataclass(frozen=True)
class QualityReport:
    schema_version: int
    asset_id: str
    request_fingerprint: str
    deterministic_status: QualityStatus
    visual_status: QualityStatus
    deterministic_checks: tuple[QualityCheck, ...]
    visual_checks: tuple[QualityCheck, ...]

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        if not isinstance(self.asset_id, str) or not self.asset_id.strip():
            raise ValueError("asset_id must not be empty")
        if not isinstance(self.request_fingerprint, str) or len(self.request_fingerprint) != 64:
            raise ValueError("request_fingerprint must be a SHA-256 hex digest")
        if not all(isinstance(item, QualityCheck) for item in (*self.deterministic_checks, *self.visual_checks)):
            raise TypeError("quality checks must contain QualityCheck objects")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "asset_id": self.asset_id,
            "request_fingerprint": self.request_fingerprint,
            "deterministic_status": self.deterministic_status.value,
            "visual_status": self.visual_status.value,
            "deterministic_checks": [item.to_dict() for item in self.deterministic_checks],
            "visual_checks": [item.to_dict() for item in self.visual_checks],
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "QualityReport":
        if not isinstance(value, dict):
            raise TypeError("QualityReport payload must be an object")
        return cls(
            schema_version=value["schema_version"],
            asset_id=value["asset_id"],
            request_fingerprint=value["request_fingerprint"],
            deterministic_status=QualityStatus(value["deterministic_status"]),
            visual_status=QualityStatus(value["visual_status"]),
            deterministic_checks=tuple(QualityCheck.from_dict(item) for item in value["deterministic_checks"]),
            visual_checks=tuple(QualityCheck.from_dict(item) for item in value["visual_checks"]),
        )
