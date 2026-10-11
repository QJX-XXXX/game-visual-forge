from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any


REQUIRED_AUDIO_CHECKS = frozenset({
    "prompt-and-action-match",
    "transient-and-impact-clarity",
    "noise-and-generation-artifacts",
    "unwanted-speech-or-music",
    "spatial-and-channel-suitability",
    "loop-or-tail-quality",
})


def _digest(value: str, field: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError(f"{field} must be a SHA-256 hex digest")
    return value


@dataclass(frozen=True)
class AudioReview:
    schema_version: int
    request_fingerprint: str
    selected_candidate_id: str
    quality_report_sha256: str
    artifact_sha256: dict[str, str]
    checks: dict[str, bool]
    reviewed_at: str

    @classmethod
    def create(cls, *, request_fingerprint: str, selected_candidate_id: str, quality_report_sha256: str, artifact_sha256: dict[str, str], checks: dict[str, bool], reviewed_at: str) -> "AudioReview":
        if set(checks) != REQUIRED_AUDIO_CHECKS:
            raise ValueError("review must contain exactly the six required audio checks")
        if not all(isinstance(value, bool) for value in checks.values()):
            raise TypeError("audio review checks must be boolean")
        _digest(request_fingerprint, "request_fingerprint")
        _digest(quality_report_sha256, "quality_report_sha256")
        for key, value in artifact_sha256.items():
            _digest(value, f"artifact_sha256.{key}")
        if not reviewed_at.endswith("Z"):
            raise ValueError("reviewed_at must be a UTC timestamp")
        return cls(1, request_fingerprint, selected_candidate_id, quality_report_sha256, dict(artifact_sha256), dict(checks), reviewed_at)

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": 1, "request_fingerprint": self.request_fingerprint, "selected_candidate_id": self.selected_candidate_id, "quality_report_sha256": self.quality_report_sha256, "artifact_sha256": self.artifact_sha256, "checks": self.checks, "reviewed_at": self.reviewed_at}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AudioReview":
        return cls.create(request_fingerprint=str(value["request_fingerprint"]), selected_candidate_id=str(value["selected_candidate_id"]), quality_report_sha256=str(value["quality_report_sha256"]), artifact_sha256=dict(value["artifact_sha256"]), checks=dict(value["checks"]), reviewed_at=str(value["reviewed_at"]))


@dataclass(frozen=True)
class AudioManifest:
    schema_version: int
    asset_id: str
    request_fingerprint: str
    selected_candidate_id: str
    files: dict[str, str]
    sha256: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class UnityAudioManifest:
    schema_version: int
    asset_id: str
    wav_path: str
    profile: str
    importer: dict[str, Any]
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class AudioSourcePlacement:
    schema_version: int
    asset_id: str
    source_name: str
    clip_path: str
    volume: float
    play_on_awake: bool
    loop: bool
    spatial_mode: str
    min_distance: float
    max_distance: float

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()
