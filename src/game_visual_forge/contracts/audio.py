from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .pathing import normalize_repo_relative_path
from ..jobs.fingerprints import fingerprint_request


_SLUG = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must not be empty")
    return value


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field} must be a number")
    return float(value)


def _optional_path(value: Any, field: str) -> str | None:
    return None if value is None else normalize_repo_relative_path(_string(value, field), field_name=field)


class AudioGenerationMode(StrEnum):
    TEXT_TO_AUDIO = "text-to-audio"
    REDRAW = "redraw"
    INPAINT = "inpaint"
    CONTINUE = "continue"


class AudioUsageProfile(StrEnum):
    UI = "ui"
    ONE_SHOT = "one-shot"
    SCENE = "scene"
    LOOPING_AMBIENCE = "looping-ambience"


class AudioSpatialMode(StrEnum):
    TWO_D = "2d"
    THREE_D = "3d"


class AudioIntakeStatus(StrEnum):
    NEEDS_USER_INPUT = "needs_user_input"
    NEEDS_USER_CONFIRMATION = "needs_user_confirmation"
    PLANNED = "planned"


class AudioQuestionGroup(StrEnum):
    SOUND = "sound"
    MODE_AND_SOURCE = "mode-and-source"
    DELIVERY = "delivery"


@dataclass(frozen=True)
class AudioRequest:
    schema_version: int
    asset_id: str
    mode: AudioGenerationMode
    prompt: str
    output_dir: str
    duration_seconds: float
    usage_profile: AudioUsageProfile
    spatial_mode: AudioSpatialMode
    loop: bool
    candidate_count: int
    source_path: str | None = None
    redraw_strength: float | None = None
    edit_start_seconds: float | None = None
    edit_end_seconds: float | None = None
    join_guard_ms: int = 20
    loop_analysis_ms: int = 50
    loop_crossfade_ms: int = 20
    unity_project_path: str | None = None
    unity_generated_root: str | None = None
    unity_import_requested: bool = False
    unity_scene_placement_requested: bool = False
    audio_source_name: str | None = None
    volume: float = 1.0
    play_on_awake: bool = False
    min_distance: float = 1.0
    max_distance: float = 25.0

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        if not isinstance(self.asset_id, str) or not _SLUG.fullmatch(self.asset_id):
            raise ValueError("asset_id must be a lowercase slug")
        _string(self.prompt, "prompt")
        object.__setattr__(self, "output_dir", normalize_repo_relative_path(self.output_dir, field_name="output_dir"))
        if not isinstance(self.mode, AudioGenerationMode):
            raise TypeError("mode must be AudioGenerationMode")
        if not isinstance(self.usage_profile, AudioUsageProfile):
            raise TypeError("usage_profile must be AudioUsageProfile")
        if not isinstance(self.spatial_mode, AudioSpatialMode):
            raise TypeError("spatial_mode must be AudioSpatialMode")
        if not isinstance(self.loop, bool):
            raise TypeError("loop must be a boolean")
        duration = _number(self.duration_seconds, "duration_seconds")
        if not 0 < duration <= 120:
            raise ValueError("duration_seconds must be greater than 0 and no greater than 120")
        object.__setattr__(self, "duration_seconds", duration)
        if isinstance(self.candidate_count, bool) or not isinstance(self.candidate_count, int):
            raise TypeError("candidate_count must be an integer")
        if not 1 <= self.candidate_count <= 8:
            raise ValueError("candidate_count must be between 1 and 8")
        if self.source_path is not None:
            object.__setattr__(self, "source_path", _optional_path(self.source_path, "source_path"))
        if self.mode is AudioGenerationMode.TEXT_TO_AUDIO and self.source_path is not None:
            raise ValueError("text-to-audio must not provide source_path")
        if self.mode is not AudioGenerationMode.TEXT_TO_AUDIO and self.source_path is None:
            raise ValueError("source_path is required for redraw, inpaint, and continue")
        if self.mode is AudioGenerationMode.INPAINT:
            if self.edit_start_seconds is None or self.edit_end_seconds is None:
                raise ValueError("edit start and edit end are required for inpaint")
        elif self.edit_start_seconds is not None or self.edit_end_seconds is not None:
            raise ValueError("edit bounds are only valid for inpaint")
        if self.edit_start_seconds is not None:
            start = _number(self.edit_start_seconds, "edit_start_seconds")
            end = _number(self.edit_end_seconds, "edit_end_seconds")
            if start < 0 or end <= start:
                raise ValueError("edit bounds must be non-negative and ordered")
            object.__setattr__(self, "edit_start_seconds", start)
            object.__setattr__(self, "edit_end_seconds", end)
        if self.redraw_strength is not None:
            strength = _number(self.redraw_strength, "redraw_strength")
            if not 0 < strength <= 1:
                raise ValueError("redraw_strength must be in (0, 1]")
            object.__setattr__(self, "redraw_strength", strength)
        elif self.mode is AudioGenerationMode.REDRAW:
            object.__setattr__(self, "redraw_strength", 0.5)
        for field in ("join_guard_ms", "loop_analysis_ms", "loop_crossfade_ms"):
            value = getattr(self, field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{field} must be a non-negative integer")
        for field in ("unity_project_path", "unity_generated_root"):
            value = getattr(self, field)
            if value is not None:
                object.__setattr__(self, field, _optional_path(value, field))
        if not isinstance(self.unity_import_requested, bool) or not isinstance(self.unity_scene_placement_requested, bool):
            raise TypeError("Unity request flags must be booleans")
        if self.unity_scene_placement_requested and not self.unity_import_requested:
            raise ValueError("unity_import_requested is required for scene placement")
        if self.audio_source_name is not None:
            _string(self.audio_source_name, "audio_source_name")
        volume = _number(self.volume, "volume")
        if not 0 <= volume <= 1:
            raise ValueError("volume must be in [0, 1]")
        object.__setattr__(self, "volume", volume)
        minimum = _number(self.min_distance, "min_distance")
        maximum = _number(self.max_distance, "max_distance")
        if minimum <= 0 or maximum <= minimum:
            raise ValueError("distance values must be positive and ordered")
        object.__setattr__(self, "min_distance", minimum)
        object.__setattr__(self, "max_distance", maximum)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "asset_id": self.asset_id,
            "mode": self.mode.value,
            "prompt": self.prompt,
            "output_dir": self.output_dir,
            "duration_seconds": self.duration_seconds,
            "usage_profile": self.usage_profile.value,
            "spatial_mode": self.spatial_mode.value,
            "loop": self.loop,
            "candidate_count": self.candidate_count,
            "source_path": self.source_path,
            "redraw_strength": self.redraw_strength,
            "edit_start_seconds": self.edit_start_seconds,
            "edit_end_seconds": self.edit_end_seconds,
            "join_guard_ms": self.join_guard_ms,
            "loop_analysis_ms": self.loop_analysis_ms,
            "loop_crossfade_ms": self.loop_crossfade_ms,
            "unity_project_path": self.unity_project_path,
            "unity_generated_root": self.unity_generated_root,
            "unity_import_requested": self.unity_import_requested,
            "unity_scene_placement_requested": self.unity_scene_placement_requested,
            "audio_source_name": self.audio_source_name,
            "volume": self.volume,
            "play_on_awake": self.play_on_awake,
            "min_distance": self.min_distance,
            "max_distance": self.max_distance,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AudioRequest":
        if not isinstance(value, dict):
            raise TypeError("AudioRequest payload must be an object")
        mode = AudioGenerationMode(value["mode"])
        count = value.get("candidate_count")
        if count is None:
            count = 3 if mode in {AudioGenerationMode.TEXT_TO_AUDIO, AudioGenerationMode.REDRAW} else 1
        return cls(
            schema_version=int(value["schema_version"]),
            asset_id=_string(value["asset_id"], "asset_id"),
            mode=mode,
            prompt=_string(value["prompt"], "prompt"),
            output_dir=_string(value["output_dir"], "output_dir"),
            duration_seconds=value["duration_seconds"],
            usage_profile=AudioUsageProfile(value["usage_profile"]),
            spatial_mode=AudioSpatialMode(value["spatial_mode"]),
            loop=value.get("loop", False),
            candidate_count=count,
            source_path=value.get("source_path"),
            redraw_strength=value.get("redraw_strength"),
            edit_start_seconds=value.get("edit_start_seconds"),
            edit_end_seconds=value.get("edit_end_seconds"),
            join_guard_ms=value.get("join_guard_ms", 20),
            loop_analysis_ms=value.get("loop_analysis_ms", 50),
            loop_crossfade_ms=value.get("loop_crossfade_ms", 20),
            unity_project_path=value.get("unity_project_path"),
            unity_generated_root=value.get("unity_generated_root"),
            unity_import_requested=value.get("unity_import_requested", False),
            unity_scene_placement_requested=value.get("unity_scene_placement_requested", False),
            audio_source_name=value.get("audio_source_name"),
            volume=value.get("volume", 1.0),
            play_on_awake=value.get("play_on_awake", False),
            min_distance=value.get("min_distance", 1.0),
            max_distance=value.get("max_distance", 25.0),
        )


@dataclass(frozen=True)
class AudioIntakeAssessment:
    status: AudioIntakeStatus
    request: AudioRequest | None = None
    missing_groups: tuple[AudioQuestionGroup, ...] = ()
    confirmation_summary: str = ""
    confirmation_sha256: str = ""


@dataclass(frozen=True)
class AudioRouteDecision:
    schema_version: int
    request_fingerprint: str
    selected_provider: str
    requires_user_action: bool
    requires_paid_confirmation: bool
    reason: str


def canonical_audio_confirmation_summary(request: AudioRequest) -> str:
    return json.dumps(request.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def audio_confirmation_sha256(request: AudioRequest) -> str:
    return hashlib.sha256(canonical_audio_confirmation_summary(request).encode("utf-8")).hexdigest()


def _missing_groups(raw: dict[str, Any]) -> tuple[AudioQuestionGroup, ...]:
    missing: list[AudioQuestionGroup] = []
    if not all(raw.get(key) not in (None, "") for key in ("prompt", "duration_seconds", "usage_profile", "spatial_mode")):
        missing.append(AudioQuestionGroup.SOUND)
    if not raw.get("mode"):
        missing.append(AudioQuestionGroup.MODE_AND_SOURCE)
    else:
        try:
            mode = AudioGenerationMode(raw["mode"])
        except ValueError:
            missing.append(AudioQuestionGroup.MODE_AND_SOURCE)
        else:
            if mode is not AudioGenerationMode.TEXT_TO_AUDIO and not raw.get("source_path"):
                missing.append(AudioQuestionGroup.MODE_AND_SOURCE)
            if mode is AudioGenerationMode.INPAINT and (raw.get("edit_start_seconds") is None or raw.get("edit_end_seconds") is None):
                if AudioQuestionGroup.MODE_AND_SOURCE not in missing:
                    missing.append(AudioQuestionGroup.MODE_AND_SOURCE)
    if not raw.get("output_dir"):
        missing.append(AudioQuestionGroup.DELIVERY)
    return tuple(missing)


def assess_audio_intake(raw: dict[str, Any], confirmed_sha256: str | None = None) -> AudioIntakeAssessment:
    missing = _missing_groups(raw)
    if missing:
        return AudioIntakeAssessment(status=AudioIntakeStatus.NEEDS_USER_INPUT, missing_groups=missing)
    request = AudioRequest.from_dict(raw)
    summary = canonical_audio_confirmation_summary(request)
    digest = audio_confirmation_sha256(request)
    status = AudioIntakeStatus.PLANNED if confirmed_sha256 == digest else AudioIntakeStatus.NEEDS_USER_CONFIRMATION
    return AudioIntakeAssessment(status=status, request=request, confirmation_summary=summary, confirmation_sha256=digest)


def route_audio(request: AudioRequest, preflight: Any | None) -> AudioRouteDecision:
    digest = fingerprint_request(request.to_dict())
    if preflight is None or not getattr(preflight, "available", False):
        return AudioRouteDecision(1, digest, "stable-audio-local", True, False, "provider-preflight-required")
    if not getattr(preflight, "model_local", False):
        return AudioRouteDecision(1, digest, "stable-audio-local", True, False, "local-model-required")
    return AudioRouteDecision(1, digest, "stable-audio-local", False, False, "local-small-sfx-ready")
