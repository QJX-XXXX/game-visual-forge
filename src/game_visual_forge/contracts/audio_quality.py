from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AudioQualityReport:
    schema_version: int
    request_fingerprint: str
    status: str
    failures: tuple[str, ...]
    warnings: tuple[str, ...]
    artifacts: dict[str, Any]
    source_hash: str | None = None

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        if self.status not in {"passed", "failed"}:
            raise ValueError("quality status must be passed or failed")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "request_fingerprint": self.request_fingerprint,
            "status": self.status,
            "failures": list(self.failures),
            "warnings": list(self.warnings),
            "artifacts": self.artifacts,
            "source_hash": self.source_hash,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AudioQualityReport":
        return cls(1, str(value["request_fingerprint"]), str(value["status"]), tuple(value.get("failures", [])), tuple(value.get("warnings", [])), dict(value.get("artifacts", {})), value.get("source_hash"))
