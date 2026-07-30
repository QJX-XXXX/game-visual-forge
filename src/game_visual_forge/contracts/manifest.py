from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


_DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}")


def _normalize_repo_path(value: str, *, field_name: str) -> str:
    normalized = value.replace("\\", "/").strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
        raise ValueError(f"{field_name} must be repository-relative")
    return normalized


@dataclass(frozen=True)
class ArtifactRecord:
    role: str
    path: str
    sha256: str

    def __post_init__(self) -> None:
        if not self.role.strip():
            raise ValueError("artifact role must not be empty")
        object.__setattr__(self, "path", _normalize_repo_path(self.path, field_name="path"))
        if not _DIGEST_PATTERN.fullmatch(self.sha256):
            raise ValueError("artifact sha256 must be a 64-character digest")

    def to_dict(self) -> dict[str, str]:
        return {
            "role": self.role,
            "path": self.path,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class AssetManifest:
    schema_version: int
    asset_id: str
    source_type: str
    provider: str | None
    model: str | None
    artifacts: tuple[ArtifactRecord, ...]
    processing_steps: tuple[str, ...]
    quality_status: str

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        if not self.asset_id.strip():
            raise ValueError("asset_id must not be empty")
        if not self.source_type.strip():
            raise ValueError("source_type must not be empty")
        if self.quality_status not in {"passed", "failed", "needs_attention"}:
            raise ValueError("unsupported quality_status")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "asset_id": self.asset_id,
            "source_type": self.source_type,
            "provider": self.provider,
            "model": self.model,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "processing_steps": list(self.processing_steps),
            "quality_status": self.quality_status,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AssetManifest":
        return cls(
            schema_version=int(value["schema_version"]),
            asset_id=str(value["asset_id"]),
            source_type=str(value["source_type"]),
            provider=str(value["provider"]) if value.get("provider") is not None else None,
            model=str(value["model"]) if value.get("model") is not None else None,
            artifacts=tuple(
                ArtifactRecord(
                    role=str(item["role"]),
                    path=str(item["path"]),
                    sha256=str(item["sha256"]),
                )
                for item in value["artifacts"]
            ),
            processing_steps=tuple(str(item) for item in value["processing_steps"]),
            quality_status=str(value["quality_status"]),
        )
