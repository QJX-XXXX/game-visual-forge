from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Mapping

from .pathing import normalize_repo_relative_path


def music_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{field} must be a finite number")
    return float(value)


def digest(value: str, field: str = "sha256") -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError(f"{field} must be a SHA-256 digest")
    return value


class MusicUsage(StrEnum):
    BGM_LOOP = "bgm-loop"
    BGM_LINEAR = "bgm-linear"
    STANDALONE_INSTRUMENTAL = "standalone-instrumental"


class MusicVocalPolicy(StrEnum):
    INSTRUMENTAL = "instrumental"
    VOCALS_ALLOWED = "vocals-allowed"
    VOCALS_REQUIRED = "vocals-required"


@dataclass(frozen=True)
class MusicRequest:
    schema_version: int
    asset_id: str
    brief: str
    usage: MusicUsage
    vocal_policy: MusicVocalPolicy
    target_duration_seconds: float
    candidate_count: int
    output_dir: str
    lyrics: str | None = None
    tempo_bpm: float | None = None
    key: str | None = None
    instruments: tuple[str, ...] = ()
    exclusions: tuple[str, ...] = ()
    unity_import_requested: bool = False

    def __post_init__(self):
        if self.schema_version != 1 or isinstance(self.schema_version, bool):
            raise ValueError("schema_version must be 1")
        if not isinstance(self.asset_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", self.asset_id):
            raise ValueError("asset_id must be a lowercase slug")
        if not isinstance(self.brief, str) or not self.brief.strip():
            raise ValueError("brief must not be empty")
        if not isinstance(self.usage, MusicUsage) or not isinstance(self.vocal_policy, MusicVocalPolicy):
            raise TypeError("usage and vocal_policy must be music enums")
        duration = finite_number(self.target_duration_seconds, "target_duration_seconds")
        if not 0 < duration <= 380:
            raise ValueError("target_duration_seconds must be in (0, 380]")
        object.__setattr__(self, "target_duration_seconds", duration)
        if isinstance(self.candidate_count, bool) or not isinstance(self.candidate_count, int) or not 1 <= self.candidate_count <= 8:
            raise ValueError("candidate_count must be an integer between 1 and 8")
        object.__setattr__(self, "output_dir", normalize_repo_relative_path(self.output_dir, field_name="output_dir"))
        if self.lyrics is not None and (not isinstance(self.lyrics, str) or not self.lyrics.strip()):
            raise ValueError("lyrics must be a non-empty string or null")
        if self.usage is MusicUsage.STANDALONE_INSTRUMENTAL and self.vocal_policy is not MusicVocalPolicy.INSTRUMENTAL:
            raise ValueError("standalone-instrumental cannot allow vocals")
        if self.vocal_policy is MusicVocalPolicy.INSTRUMENTAL and self.lyrics is not None:
            raise ValueError("instrumental requests cannot contain lyrics")
        if self.tempo_bpm is not None and finite_number(self.tempo_bpm, "tempo_bpm") <= 0:
            raise ValueError("tempo_bpm must be positive")
        if self.key is not None and (not isinstance(self.key, str) or not self.key.strip()):
            raise ValueError("key must be non-empty or null")
        for field in ("instruments", "exclusions"):
            items = getattr(self, field)
            if not isinstance(items, (tuple, list)) or any(not isinstance(i, str) or not i.strip() for i in items):
                raise ValueError(f"{field} must be a list of non-empty strings")
            object.__setattr__(self, field, tuple(items))
        if not isinstance(self.unity_import_requested, bool):
            raise ValueError("unity_import_requested must be boolean")

    def to_dict(self):
        return {**asdict(self), "usage": self.usage.value, "vocal_policy": self.vocal_policy.value, "instruments": list(self.instruments), "exclusions": list(self.exclusions)}

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict):
            raise TypeError("MusicRequest must be an object")
        return cls(value.get("schema_version", 1), value["asset_id"], value["brief"], MusicUsage(value.get("usage", "bgm-linear")), MusicVocalPolicy(value.get("vocal_policy", "instrumental")), value["target_duration_seconds"], value.get("candidate_count", 1), value["output_dir"], value.get("lyrics"), value.get("tempo_bpm"), value.get("key"), value.get("instruments", ()), value.get("exclusions", ()), value.get("unity_import_requested", False))


@dataclass(frozen=True)
class MusicProcessingOptions:
    duration_policy: str = "natural"
    trim_start_seconds: float | None = None
    trim_end_seconds: float | None = None
    loop_start_seconds: float | None = None
    loop_end_seconds: float | None = None
    loop_crossfade_ms: float = 0
    unity_import_requested: bool = False

    def __post_init__(self):
        if self.duration_policy not in {"natural", "trim"}:
            raise ValueError("duration_policy must be natural or trim")
        for prefix in ("trim", "loop"):
            start, end = getattr(self, prefix + "_start_seconds"), getattr(self, prefix + "_end_seconds")
            if (start is None) != (end is None):
                raise ValueError(f"{prefix} requires both interval bounds")
            if start is not None and (finite_number(start, prefix) < 0 or finite_number(end, prefix) <= start):
                raise ValueError(f"{prefix} interval must be non-negative and ordered")
        if (self.duration_policy == "trim") != (self.trim_start_seconds is not None):
            raise ValueError("trim interval requires duration_policy=trim")
        if finite_number(self.loop_crossfade_ms, "loop_crossfade_ms") < 0:
            raise ValueError("loop_crossfade_ms must be non-negative")
        if self.loop_crossfade_ms and self.loop_start_seconds is None:
            raise ValueError("crossfade requires a loop interval")
        if not isinstance(self.unity_import_requested, bool):
            raise ValueError("unity_import_requested must be boolean")

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        return cls(**value)


@dataclass(frozen=True)
class MusicPromptPackage:
    original_brief: str
    provider: str
    caption: str
    lyrics: str | None
    vocal_policy: str

    def to_dict(self):
        return asdict(self)

    @property
    def sha256(self):
        return music_hash(self.to_dict())


@dataclass(frozen=True)
class MusicRouteDecision:
    selected_provider: Any
    status: str
    reason: str
    requires_paid_confirmation: bool

    def to_dict(self):
        return asdict(self)


def build_music_prompt_package(request, provider, caption):
    if not isinstance(caption, str) or not caption.strip():
        raise ValueError("caption must not be empty")
    vocal = "Instrumental, no vocals, no humming, no choir, no speech" if request.vocal_policy is MusicVocalPolicy.INSTRUMENTAL else f"Vocal policy: {request.vocal_policy.value}"
    details = [caption, f"Original brief: {request.brief}", vocal]
    if request.tempo_bpm is not None:
        details.append(f"Tempo: {request.tempo_bpm} BPM")
    if request.key:
        details.append(f"Key: {request.key}")
    if request.instruments:
        details.append("Required instruments: " + ", ".join(request.instruments))
    if request.exclusions:
        details.append("Exclude: " + ", ".join(request.exclusions))
    lyrics = "[instrumental]" if request.vocal_policy is MusicVocalPolicy.INSTRUMENTAL else request.lyrics
    return MusicPromptPackage(request.brief, provider.value, "; ".join(details), lyrics, request.vocal_policy.value)


def generation_fingerprint(request, prompt, capability, parameters: Mapping[str, Any]):
    from .music_provider import scan_safe
    scan_safe(parameters)
    creation = request.to_dict()
    for key in ("asset_id", "output_dir", "unity_import_requested"):
        creation.pop(key)
    return music_hash({"request": creation, "prompt": prompt.to_dict(), "capability": capability.to_dict(), "parameters": dict(parameters)})


@dataclass(frozen=True)
class MusicSourceRecord:
    path: str
    sha256: str
    codec_name: str
    sample_rate: int
    channels: int
    duration_seconds: float
    provider: str
    attempt_id: str
    candidate_id: str

    def __post_init__(self):
        object.__setattr__(self, "path", normalize_repo_relative_path(self.path, field_name="source path"))
        digest(self.sha256)
        if not self.codec_name or self.sample_rate <= 0 or self.channels <= 0 or finite_number(self.duration_seconds, "source duration") <= 0:
            raise ValueError("source metadata is invalid")

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        return cls(**value)


@dataclass(frozen=True)
class MusicProcessingResult:
    source_sha256: str
    processed_path: str
    processed_sha256: str
    processing_fingerprint: str
    sample_rate: int
    channels: int
    duration_seconds: float
    original_sample_rate: int
    original_channels: int
    gain_db: float = 0.0
    loop_evidence_path: str | None = None
    loop_evidence_sha256: str | None = None
    source_path: str | None = None

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class MusicLoopEvidence:
    source_sha256: str
    start_seconds: float
    end_seconds: float
    crossfade_ms: float
    effective_frame_count: int
    boundary_error: float
    boundary_preview_path: str
    three_round_path: str
    evidence_sha256: str

    def to_dict(self):
        return asdict(self)
