from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .quality import QualityCheck, QualityStatus


@dataclass(frozen=True)
class VideoQualityReport:
    schema_version: int
    asset_id: str
    request_fingerprint: str
    deterministic_status: QualityStatus
    temporal_status: QualityStatus
    visual_status: QualityStatus
    deterministic_checks: tuple[QualityCheck, ...]
    temporal_metrics: dict[str, Any]
    visual_checks: dict[str, bool]
    review_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        if not self.asset_id.strip():
            raise ValueError("asset_id must not be empty")
        if len(self.request_fingerprint) != 64:
            raise ValueError("request_fingerprint must be a SHA-256 hex digest")
        if not all(isinstance(item, QualityCheck) for item in self.deterministic_checks):
            raise TypeError("deterministic_checks must contain QualityCheck objects")

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": 1, "asset_id": self.asset_id, "request_fingerprint": self.request_fingerprint, "deterministic_status": self.deterministic_status.value, "temporal_status": self.temporal_status.value, "visual_status": self.visual_status.value, "deterministic_checks": [item.to_dict() for item in self.deterministic_checks], "temporal_metrics": self.temporal_metrics, "visual_checks": self.visual_checks, "review_sha256": self.review_sha256}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "VideoQualityReport":
        return cls(schema_version=int(value["schema_version"]), asset_id=str(value["asset_id"]), request_fingerprint=str(value["request_fingerprint"]), deterministic_status=QualityStatus(value["deterministic_status"]), temporal_status=QualityStatus(value["temporal_status"]), visual_status=QualityStatus(value["visual_status"]), deterministic_checks=tuple(QualityCheck.from_dict(item) for item in value["deterministic_checks"]), temporal_metrics=dict(value.get("temporal_metrics", {})), visual_checks={str(key): bool(item) for key, item in value.get("visual_checks", {}).items()}, review_sha256=value.get("review_sha256"))
