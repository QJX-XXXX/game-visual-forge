from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_DIGEST = re.compile(r"[0-9a-f]{64}")


def _digest(value: str, field: str) -> str:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise ValueError(f"{field} must be a SHA-256 hex digest")
    return value


@dataclass(frozen=True)
class VideoMotionReview:
    schema_version: int
    request_fingerprint: str
    source_sha256: str
    quality_report_sha256: str
    artifact_sha256: dict[str, str]
    checks: dict[str, bool]
    approved: bool
    reviewed_at: str
    review_sha256: str

    @classmethod
    def create(cls, *, request_fingerprint: str, source_sha256: str, quality_report_sha256: str, artifact_sha256: dict[str, str], checks: dict[str, bool], approved: bool, reviewed_at: str) -> "VideoMotionReview":
        payload = {"schema_version": 1, "request_fingerprint": request_fingerprint, "source_sha256": source_sha256, "quality_report_sha256": quality_report_sha256, "artifact_sha256": dict(sorted(artifact_sha256.items())), "checks": dict(sorted(checks.items())), "approved": approved, "reviewed_at": reviewed_at}
        digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        return cls(1, request_fingerprint, source_sha256, quality_report_sha256, dict(sorted(artifact_sha256.items())), dict(sorted(checks.items())), approved, reviewed_at, digest)

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        _digest(self.request_fingerprint, "request_fingerprint")
        _digest(self.source_sha256, "source_sha256")
        _digest(self.quality_report_sha256, "quality_report_sha256")
        for key, value in self.artifact_sha256.items():
            if not key.strip():
                raise ValueError("artifact names must not be empty")
            _digest(value, f"artifact_sha256.{key}")
        if not all(isinstance(value, bool) for value in self.checks.values()):
            raise TypeError("review checks must be booleans")
        _digest(self.review_sha256, "review_sha256")

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": 1, "request_fingerprint": self.request_fingerprint, "source_sha256": self.source_sha256, "quality_report_sha256": self.quality_report_sha256, "artifact_sha256": self.artifact_sha256, "checks": self.checks, "approved": self.approved, "reviewed_at": self.reviewed_at, "review_sha256": self.review_sha256}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "VideoMotionReview":
        result = cls.create(request_fingerprint=str(value["request_fingerprint"]), source_sha256=str(value["source_sha256"]), quality_report_sha256=str(value["quality_report_sha256"]), artifact_sha256={str(key): str(item) for key, item in value["artifact_sha256"].items()}, checks={str(key): bool(item) for key, item in value["checks"].items()}, approved=bool(value["approved"]), reviewed_at=str(value["reviewed_at"]))
        if result.review_sha256 != value["review_sha256"]:
            raise ValueError("review hash does not match")
        return result
