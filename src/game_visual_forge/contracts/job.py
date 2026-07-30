from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from .pathing import normalize_repo_relative_path


_UTC_RFC3339_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$"
)


def _validate_timestamp(value: str, *, field_name: str) -> str:
    if not value.endswith("Z"):
        raise ValueError("timestamps must be UTC RFC 3339 values ending in Z")
    if not _UTC_RFC3339_PATTERN.fullmatch(value):
        raise ValueError(f"{field_name} must be a UTC RFC 3339 timestamp")
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ValueError(f"{field_name} must be a UTC RFC 3339 timestamp") from error
    return value


class JobStatus(StrEnum):
    PLANNED = "planned"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    READY = "ready"
    SUBMITTING = "submitting"
    RUNNING = "running"
    DOWNLOADING = "downloading"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    SUBMISSION_UNKNOWN = "submission_unknown"
    NEEDS_ATTENTION = "needs_attention"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class JobState:
    schema_version: int
    job_id: str
    asset_id: str
    status: JobStatus
    created_at: str
    updated_at: str
    request_fingerprint: str
    provider: str | None = None
    external_task_id: str | None = None
    error_code: str | None = None
    ready_provenance: str | None = None
    artifact_paths: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        object.__setattr__(
            self,
            "created_at",
            _validate_timestamp(self.created_at, field_name="created_at"),
        )
        object.__setattr__(
            self,
            "updated_at",
            _validate_timestamp(self.updated_at, field_name="updated_at"),
        )
        if len(self.request_fingerprint) != 64:
            raise ValueError("request_fingerprint must be a SHA-256 hex digest")
        try:
            int(self.request_fingerprint, 16)
        except ValueError as error:
            raise ValueError(
                "request_fingerprint must be a SHA-256 hex digest"
            ) from error
        object.__setattr__(
            self,
            "artifact_paths",
            tuple(
                normalize_repo_relative_path(path, field_name="artifact_paths")
                for path in self.artifact_paths
            ),
        )
        if self.ready_provenance is not None:
            try:
                JobStatus(self.ready_provenance)
            except ValueError as error:
                raise ValueError("ready_provenance must name a valid job status") from error

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "job_id": self.job_id,
            "asset_id": self.asset_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "request_fingerprint": self.request_fingerprint,
            "provider": self.provider,
            "external_task_id": self.external_task_id,
            "error_code": self.error_code,
            "ready_provenance": self.ready_provenance,
            "artifact_paths": list(self.artifact_paths),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "JobState":
        if int(value["schema_version"]) != 1:
            raise ValueError("unsupported JobState schema_version")
        return cls(
            schema_version=1,
            job_id=str(value["job_id"]),
            asset_id=str(value["asset_id"]),
            status=JobStatus(value["status"]),
            created_at=str(value["created_at"]),
            updated_at=str(value["updated_at"]),
            request_fingerprint=str(value["request_fingerprint"]),
            provider=str(value["provider"]) if value.get("provider") is not None else None,
            external_task_id=(
                str(value["external_task_id"])
                if value.get("external_task_id") is not None
                else None
            ),
            error_code=str(value["error_code"]) if value.get("error_code") is not None else None,
            ready_provenance=(
                str(value["ready_provenance"])
                if value.get("ready_provenance") is not None
                else None
            ),
            artifact_paths=tuple(
                str(item) for item in value.get("artifact_paths", [])
            ),
        )
