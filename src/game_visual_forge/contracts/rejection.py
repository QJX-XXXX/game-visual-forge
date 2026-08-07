from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .job import _validate_timestamp
from .pathing import normalize_repo_relative_path


_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")


@dataclass(frozen=True)
class RejectedArtifact:
    path: str
    sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", normalize_repo_relative_path(self.path, field_name="path"))
        if not _SHA256.fullmatch(self.sha256):
            raise ValueError("sha256 must be a SHA-256 hex digest")

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "sha256": self.sha256.lower()}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RejectedArtifact":
        return cls(path=str(value["path"]), sha256=str(value["sha256"]))


@dataclass(frozen=True)
class JobRejectionRecord:
    schema_version: int
    job_id: str
    asset_id: str
    request_fingerprint: str
    rejected_at: str
    reason_code: str
    reason: str
    artifacts: tuple[RejectedArtifact, ...]

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        if not _SHA256.fullmatch(self.request_fingerprint):
            raise ValueError("request_fingerprint must be a SHA-256 hex digest")
        _validate_timestamp(self.rejected_at, field_name="rejected_at")
        if not self.reason_code.strip() or not self.reason.strip():
            raise ValueError("reason_code and reason must not be empty")
        object.__setattr__(self, "artifacts", tuple(self.artifacts))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "job_id": self.job_id,
            "asset_id": self.asset_id,
            "request_fingerprint": self.request_fingerprint.lower(),
            "rejected_at": self.rejected_at,
            "reason_code": self.reason_code,
            "reason": self.reason,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "JobRejectionRecord":
        if int(value["schema_version"]) != 1:
            raise ValueError("unsupported JobRejectionRecord schema_version")
        return cls(
            schema_version=1,
            job_id=str(value["job_id"]),
            asset_id=str(value["asset_id"]),
            request_fingerprint=str(value["request_fingerprint"]),
            rejected_at=str(value["rejected_at"]),
            reason_code=str(value["reason_code"]),
            reason=str(value["reason"]),
            artifacts=tuple(RejectedArtifact.from_dict(item) for item in value.get("artifacts", [])),
        )
