from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .pathing import normalize_repo_relative_path


_DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}")
@dataclass(frozen=True)
class ArtifactRecord:
    role: str
    path: str
    sha256: str

    def __post_init__(self) -> None:
        if not self.role.strip():
            raise ValueError("artifact role must not be empty")
        object.__setattr__(
            self,
            "path",
            normalize_repo_relative_path(self.path, field_name="path"),
        )
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
    delivery_normalization: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        if not self.asset_id.strip():
            raise ValueError("asset_id must not be empty")
        if not self.source_type.strip():
            raise ValueError("source_type must not be empty")
        if self.quality_status not in {"passed", "failed", "needs_attention"}:
            raise ValueError("unsupported quality_status")
        if not all(isinstance(item, ArtifactRecord) for item in self.artifacts):
            raise TypeError("artifacts must contain ArtifactRecord objects")
        if self.delivery_normalization is not None and not isinstance(self.delivery_normalization, dict):
            raise TypeError("delivery_normalization must be an object")
        paths = [item.path for item in self.artifacts]
        if len(paths) != len(set(paths)):
            raise ValueError("artifact paths must be unique")

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
            "delivery_normalization": self.delivery_normalization,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AssetManifest":
        if not isinstance(value, dict):
            raise TypeError("AssetManifest payload must be an object")
        artifacts = value["artifacts"]
        if not isinstance(artifacts, list):
            raise TypeError("artifacts must be a JSON array")
        return cls(
            schema_version=value["schema_version"],
            asset_id=value["asset_id"],
            source_type=value["source_type"],
            provider=value.get("provider"),
            model=value.get("model"),
            artifacts=tuple(
                ArtifactRecord(
                    role=item["role"],
                    path=item["path"],
                    sha256=item["sha256"],
                )
                for item in artifacts
            ),
            processing_steps=tuple(value["processing_steps"]),
            quality_status=value["quality_status"],
            delivery_normalization=value.get("delivery_normalization"),
        )
