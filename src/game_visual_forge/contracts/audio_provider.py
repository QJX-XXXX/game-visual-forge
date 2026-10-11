from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any

from .audio import AudioGenerationMode
from .pathing import normalize_repo_relative_path


_DIGEST = re.compile(r"[0-9a-f]{64}")
_SECRET_KEYS = {"token", "cookie", "authorization", "api_key", "access_key", "secret", "base64"}


def _digest(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise ValueError(f"{field} must be a SHA-256 hex digest")
    return value


def _timestamp(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field} must be a UTC RFC 3339 timestamp")
    return value


def _scan_safe(value: Any, path: str = "parameters") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in _SECRET_KEYS:
                raise ValueError(f"secret field is not allowed: {path}.{key}")
            _scan_safe(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _scan_safe(child, f"{path}[{index}]")
    elif isinstance(value, str) and "data:" in value.lower() and ";base64," in value.lower():
        raise ValueError(f"base64 media is not allowed: {path}")


class AudioAttemptStatus(StrEnum):
    PREPARED = "prepared"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    GENERATION_UNKNOWN = "generation_unknown"


@dataclass(frozen=True)
class AudioProviderPreflight:
    schema_version: int
    provider: str
    available: bool
    python_executable: str | None
    package: str | None
    package_version: str | None
    model_id: str
    model_repository: str
    model_local: bool
    ffmpeg_available: bool
    ffprobe_available: bool
    reason: str | None
    runtime_root: str | None = None
    model_cache: str | None = None
    cuda_available: bool | None = None
    device_name: str | None = None

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        if self.provider != "stable-audio-local":
            raise ValueError("provider must be stable-audio-local")
        if self.model_id != "small-sfx":
            raise ValueError("model_id must be small-sfx")
        if self.model_repository != "stabilityai/stable-audio-3-small-sfx":
            raise ValueError("model_repository must be stabilityai/stable-audio-3-small-sfx")

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AudioProviderPreflight":
        return cls(
            schema_version=int(value["schema_version"]),
            provider=str(value["provider"]),
            available=bool(value["available"]),
            python_executable=value.get("python_executable"),
            package=value.get("package"),
            package_version=value.get("package_version"),
            model_id=str(value["model_id"]),
            model_repository=str(value.get("model_repository", "")),
            model_local=bool(value["model_local"]),
            ffmpeg_available=bool(value["ffmpeg_available"]),
            ffprobe_available=bool(value["ffprobe_available"]),
            reason=value.get("reason"),
            runtime_root=value.get("runtime_root"),
            model_cache=value.get("model_cache"),
            cuda_available=None if value.get("cuda_available") is None else bool(value["cuda_available"]),
            device_name=value.get("device_name"),
        )


@dataclass(frozen=True)
class AudioGenerationAttempt:
    schema_version: int
    attempt_id: str
    request_fingerprint: str
    model_id: str
    mode: AudioGenerationMode
    seed: int
    parameters: dict[str, Any]
    status: AudioAttemptStatus
    created_at: str
    updated_at: str
    output_path: str | None = None
    output_sha256: str | None = None
    error_code: str | None = None

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        if not self.attempt_id.strip():
            raise ValueError("attempt_id must not be empty")
        _digest(self.request_fingerprint, "request_fingerprint")
        if self.model_id != "small-sfx":
            raise ValueError("model_id must be small-sfx")
        if not isinstance(self.seed, int) or isinstance(self.seed, bool) or not -(2**31) <= self.seed <= 2**31 - 1:
            raise ValueError("seed must be a signed 32-bit integer")
        _scan_safe(self.parameters)
        _timestamp(self.created_at, "created_at")
        _timestamp(self.updated_at, "updated_at")
        if self.output_path is not None:
            object.__setattr__(self, "output_path", normalize_repo_relative_path(self.output_path, field_name="output_path"))
        if self.output_sha256 is not None:
            _digest(self.output_sha256, "output_sha256")
        if self.status is AudioAttemptStatus.COMPLETED and (self.output_path is None or self.output_sha256 is None):
            raise ValueError("completed attempts require output path and hash")

    def assert_can_generate(self) -> None:
        if self.status is not AudioAttemptStatus.PREPARED:
            if self.status is AudioAttemptStatus.GENERATION_UNKNOWN:
                raise ValueError("generation_unknown attempts must not be resubmitted")
            raise ValueError(f"attempt status {self.status.value} is not prepared")

    def replace(self, **changes: Any) -> "AudioGenerationAttempt":
        immutable = {"attempt_id", "request_fingerprint", "model_id", "mode", "seed"}
        if immutable.intersection(changes):
            raise ValueError("audio attempt binding cannot change after preparation")
        return replace(self, **changes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "attempt_id": self.attempt_id,
            "request_fingerprint": self.request_fingerprint,
            "model_id": self.model_id,
            "mode": self.mode.value,
            "seed": self.seed,
            "parameters": self.parameters,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "output_path": self.output_path,
            "output_sha256": self.output_sha256,
            "error_code": self.error_code,
        }
    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AudioGenerationAttempt":
        return cls(
            schema_version=int(value["schema_version"]),
            attempt_id=str(value["attempt_id"]),
            request_fingerprint=str(value["request_fingerprint"]),
            model_id=str(value["model_id"]),
            mode=AudioGenerationMode(value["mode"]),
            seed=int(value["seed"]),
            parameters=dict(value["parameters"]),
            status=AudioAttemptStatus(value["status"]),
            created_at=str(value["created_at"]),
            updated_at=str(value["updated_at"]),
            output_path=value.get("output_path"),
            output_sha256=value.get("output_sha256"),
            error_code=value.get("error_code"),
        )


@dataclass(frozen=True)
class AudioCandidateRecord:
    schema_version: int
    candidate_id: str
    attempt_id: str
    seed: int
    raw_path: str
    raw_sha256: str

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        object.__setattr__(self, "raw_path", normalize_repo_relative_path(self.raw_path, field_name="raw_path"))
        _digest(self.raw_sha256, "raw_sha256")

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AudioCandidateRecord":
        return cls(1, str(value["candidate_id"]), str(value["attempt_id"]), int(value["seed"]), str(value["raw_path"]), str(value["raw_sha256"]))


@dataclass(frozen=True)
class AudioGenerationResult:
    schema_version: int
    request_fingerprint: str
    mode: AudioGenerationMode
    candidates: tuple[AudioCandidateRecord, ...]
    attempt_paths: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        _digest(self.request_fingerprint, "request_fingerprint")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "request_fingerprint": self.request_fingerprint,
            "mode": self.mode.value,
            "candidates": [item.__dict__ for item in self.candidates],
            "attempt_paths": list(self.attempt_paths),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AudioGenerationResult":
        return cls(1, str(value["request_fingerprint"]), AudioGenerationMode(value["mode"]), tuple(AudioCandidateRecord.from_dict(item) for item in value.get("candidates", [])), tuple(str(item) for item in value.get("attempt_paths", [])))
