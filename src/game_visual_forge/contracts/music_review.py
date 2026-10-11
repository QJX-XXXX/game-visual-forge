from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass

REQUIRED_MUSIC_CHECKS = frozenset({"scene-and-mood-match", "vocal-policy-match", "instrumentation-and-structure", "mix-and-generation-artifacts", "loop-or-ending-quality", "gameplay-listening-suitability"})


def _digest(value, field):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value): raise ValueError(f"{field} must be a SHA-256 digest")
    return value


@dataclass(frozen=True)
class MusicQualityReport:
    schema_version: int
    request_fingerprint: str
    processing_fingerprint: str
    status: str
    failures: tuple[str, ...]
    warnings: tuple[str, ...]
    metrics: dict
    source_sha256: str
    processed_sha256: str
    loop_evidence_sha256: str | None = None

    def __post_init__(self):
        if self.schema_version != 1 or self.status not in {"passed", "failed"}: raise ValueError("invalid music quality report")
        _digest(self.source_sha256, "source_sha256"); _digest(self.processed_sha256, "processed_sha256")

    def to_dict(self):
        value = asdict(self); value["failures"] = list(self.failures); value["warnings"] = list(self.warnings); return value

    @classmethod
    def from_dict(cls, value):
        return cls(1, str(value["request_fingerprint"]), str(value["processing_fingerprint"]), str(value["status"]), tuple(value.get("failures", ())), tuple(value.get("warnings", ())), dict(value.get("metrics", {})), str(value["source_sha256"]), str(value["processed_sha256"]), value.get("loop_evidence_sha256"))

    @property
    def sha256(self):
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class MusicReview:
    schema_version: int
    request_fingerprint: str
    processing_fingerprint: str
    quality_report_sha256: str
    artifact_sha256: dict[str, str]
    checks: dict[str, bool]
    reviewed_at: str

    @classmethod
    def create(cls, *, request_fingerprint, processing_fingerprint, quality_report_sha256, artifact_sha256, checks, reviewed_at):
        if set(checks) != REQUIRED_MUSIC_CHECKS: raise ValueError("review must contain exactly the six required music checks")
        if not all(isinstance(value, bool) for value in checks.values()): raise TypeError("music review checks must be boolean")
        _digest(request_fingerprint, "request_fingerprint"); _digest(processing_fingerprint, "processing_fingerprint"); _digest(quality_report_sha256, "quality_report_sha256")
        for key, value in artifact_sha256.items(): _digest(value, f"artifact_sha256.{key}")
        if not reviewed_at.endswith("Z"): raise ValueError("reviewed_at must be UTC")
        return cls(1, request_fingerprint, processing_fingerprint, quality_report_sha256, dict(artifact_sha256), dict(checks), reviewed_at)

    def to_dict(self): return asdict(self)

    @classmethod
    def from_dict(cls, value):
        return cls.create(request_fingerprint=str(value["request_fingerprint"]), processing_fingerprint=str(value["processing_fingerprint"]), quality_report_sha256=str(value["quality_report_sha256"]), artifact_sha256=dict(value["artifact_sha256"]), checks=dict(value["checks"]), reviewed_at=str(value["reviewed_at"]))

    def assert_current(self, processing, quality, *, repo_root=None):
        if self.processing_fingerprint != processing.processing_fingerprint or self.quality_report_sha256 != quality.sha256: raise ValueError("review is stale")
        from pathlib import Path
        import hashlib
        root = Path(repo_root or ".")
        path = Path(processing.processed_path); path = path if path.is_absolute() else root / path
        current = hashlib.sha256(path.read_bytes()).hexdigest()
        if self.artifact_sha256.get("processed") != current: raise ValueError("processed artifact changed after review")
        if processing.source_path:
            source = Path(processing.source_path); source = source if source.is_absolute() else root / source
            if self.artifact_sha256.get("source") != hashlib.sha256(source.read_bytes()).hexdigest(): raise ValueError("source artifact changed after review")
        if processing.loop_evidence_path:
            loop = Path(processing.loop_evidence_path); loop = loop if loop.is_absolute() else root / loop
            if self.artifact_sha256.get("loop_evidence") != hashlib.sha256(loop.read_bytes()).hexdigest(): raise ValueError("loop evidence changed after review")
