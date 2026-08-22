from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .pathing import normalize_repo_relative_path
from .provider import ExternalProvider


_DIGEST = re.compile(r"[0-9a-f]{64}")
_HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}")
_SLUG = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
MAX_FRAME_COUNT = 240


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    if not value.strip():
        raise ValueError(f"{field} must not be empty")
    return value


def _optional_string(value: Any, field: str) -> str | None:
    return None if value is None else _string(value, field)


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field} must be an integer")
    if value <= 0:
        raise ValueError(f"{field} must be positive")
    return value


def _optional_positive_int(value: Any, field: str) -> int | None:
    return None if value is None else _positive_int(value, field)


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field} must be a number")
    return float(value)


def _digest(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise ValueError(f"{field} must be a SHA-256 hex digest")
    return value


def _strings(value: Any, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)) or isinstance(value, str):
        raise TypeError(f"{field} must be a list of strings")
    return tuple(_string(item, field) for item in value)


class VideoSourcePreference(StrEnum):
    EXISTING_FILE = "existing-file"
    COMFYUI_H3 = "comfyui-h3"
    MINIMAX = "minimax"
    JIMENG = "jimeng"


class VideoGenerationMode(StrEnum):
    T2V = "t2v"
    I2V_FIRST = "i2v-first"
    I2V_LAST = "i2v-last"
    I2V_FIRST_TAIL = "i2v-first-tail"
    REFERENCE_TO_VIDEO = "reference-to-video"


class VideoBackgroundMode(StrEnum):
    PRESERVE = "preserve"
    CHROMA = "chroma"
    REMBG = "rembg"


class VideoProcessingMode(StrEnum):
    PIXEL = "pixel"
    HD = "hd"


class VideoAnchor(StrEnum):
    CENTER = "center"
    FEET = "feet"


class VideoOutput(StrEnum):
    FRAMES = "frames"
    STRIPS = "strips"
    SHEETS = "sheets"
    GIF = "gif"


@dataclass(frozen=True)
class VideoSpriteRequest:
    schema_version: int
    asset_id: str
    prompt: str
    output_dir: str
    source_preference: VideoSourcePreference | None
    existing_video_path: str | None = None
    provider: ExternalProvider | None = None
    backend: str | None = None
    region: str | None = None
    model: str | None = None
    action_name: str | None = None
    generation_mode: VideoGenerationMode = VideoGenerationMode.T2V
    first_frame_path: str | None = None
    last_frame_path: str | None = None
    reference_paths: tuple[str, ...] = ()
    loop: bool = True
    clip_start_seconds: float = 0.0
    clip_end_seconds: float | None = None
    frame_counts: tuple[int, ...] = (24,)
    outputs: tuple[VideoOutput, ...] = (VideoOutput.FRAMES, VideoOutput.SHEETS, VideoOutput.GIF)
    background_mode: VideoBackgroundMode = VideoBackgroundMode.REMBG
    chroma_color: str | None = None
    rembg_refinement: str | None = None
    processing_mode: VideoProcessingMode = VideoProcessingMode.HD
    canvas_width: int | None = None
    canvas_height: int | None = None
    anchor: VideoAnchor = VideoAnchor.FEET
    fit_scale: float = 0.88
    target_engine_notes: str | None = None

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        if not isinstance(self.asset_id, str) or not _SLUG.fullmatch(self.asset_id):
            raise ValueError("asset_id must be a lowercase slug")
        _string(self.prompt, "prompt")
        object.__setattr__(self, "output_dir", normalize_repo_relative_path(self.output_dir, field_name="output_dir"))
        if self.source_preference is not None and not isinstance(self.source_preference, VideoSourcePreference):
            raise TypeError("source_preference must be VideoSourcePreference")
        for field in ("existing_video_path", "first_frame_path", "last_frame_path"):
            value = getattr(self, field)
            if value is not None:
                object.__setattr__(self, field, normalize_repo_relative_path(value, field_name=field))
        object.__setattr__(self, "reference_paths", tuple(normalize_repo_relative_path(path, field_name="reference_paths") for path in _strings(self.reference_paths, "reference_paths")))
        if self.provider is not None and not isinstance(self.provider, ExternalProvider):
            raise TypeError("provider must be ExternalProvider")
        _optional_string(self.backend, "backend")
        _optional_string(self.region, "region")
        _optional_string(self.model, "model")
        _optional_string(self.action_name, "action_name")
        if not isinstance(self.generation_mode, VideoGenerationMode):
            raise TypeError("generation_mode must be VideoGenerationMode")
        if not isinstance(self.loop, bool):
            raise TypeError("loop must be a boolean")
        start = _number(self.clip_start_seconds, "clip_start_seconds")
        if start < 0:
            raise ValueError("clip_start_seconds must not be negative")
        if self.clip_end_seconds is not None:
            end = _number(self.clip_end_seconds, "clip_end_seconds")
            if end <= start:
                raise ValueError("clip_end_seconds must be greater than clip_start_seconds")
        if not self.frame_counts:
            object.__setattr__(self, "frame_counts", (24,))
        counts = tuple(sorted(set(_positive_int(item, "frame_counts") for item in self.frame_counts)))
        if any(item > MAX_FRAME_COUNT for item in counts):
            raise ValueError(f"frame_counts must not exceed {MAX_FRAME_COUNT}")
        object.__setattr__(self, "frame_counts", counts)
        if not self.outputs or not all(isinstance(item, VideoOutput) for item in self.outputs):
            raise ValueError("outputs must contain at least one VideoOutput")
        if not isinstance(self.background_mode, VideoBackgroundMode):
            raise TypeError("background_mode must be VideoBackgroundMode")
        if self.chroma_color is not None and not _HEX_COLOR.fullmatch(self.chroma_color):
            raise ValueError("chroma_color must be an RGB hex color")
        if self.background_mode is VideoBackgroundMode.CHROMA and self.chroma_color is None:
            raise ValueError("chroma_color is required for chroma background removal")
        if self.background_mode is VideoBackgroundMode.PRESERVE and self.chroma_color is not None:
            raise ValueError("chroma_color is only valid for chroma or rembg")
        if not isinstance(self.processing_mode, VideoProcessingMode):
            raise TypeError("processing_mode must be VideoProcessingMode")
        self._validate_references()
        if self.canvas_width is None and self.canvas_height is not None or self.canvas_width is not None and self.canvas_height is None:
            raise ValueError("canvas_width and canvas_height must be provided together")
        _optional_positive_int(self.canvas_width, "canvas_width")
        _optional_positive_int(self.canvas_height, "canvas_height")
        if not isinstance(self.anchor, VideoAnchor):
            raise TypeError("anchor must be VideoAnchor")
        scale = _number(self.fit_scale, "fit_scale")
        if not 0 < scale <= 1:
            raise ValueError("fit_scale must be in (0, 1]")
        _optional_string(self.target_engine_notes, "target_engine_notes")

    def _validate_references(self) -> None:
        if self.generation_mode is VideoGenerationMode.I2V_FIRST and self.first_frame_path is None:
            raise ValueError("first_frame_path is required for i2v-first")
        if self.generation_mode is VideoGenerationMode.I2V_LAST and self.last_frame_path is None:
            raise ValueError("last_frame_path is required for i2v-last")
        if self.generation_mode is VideoGenerationMode.I2V_FIRST_TAIL and (self.first_frame_path is None or self.last_frame_path is None):
            raise ValueError("first_frame_path and last_frame_path are required for i2v-first-tail")
        if self.generation_mode is VideoGenerationMode.REFERENCE_TO_VIDEO and not self.reference_paths:
            raise ValueError("reference_paths is required for reference-to-video")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "asset_id": self.asset_id,
            "prompt": self.prompt,
            "output_dir": self.output_dir,
            "source_preference": None if self.source_preference is None else self.source_preference.value,
            "existing_video_path": self.existing_video_path,
            "provider": None if self.provider is None else self.provider.value,
            "backend": self.backend,
            "region": self.region,
            "model": self.model,
            "action_name": self.action_name,
            "generation_mode": self.generation_mode.value,
            "first_frame_path": self.first_frame_path,
            "last_frame_path": self.last_frame_path,
            "reference_paths": list(self.reference_paths),
            "loop": self.loop,
            "clip_start_seconds": self.clip_start_seconds,
            "clip_end_seconds": self.clip_end_seconds,
            "frame_counts": list(self.frame_counts),
            "outputs": [item.value for item in self.outputs],
            "background_mode": self.background_mode.value,
            "chroma_color": self.chroma_color,
            "rembg_refinement": self.rembg_refinement,
            "processing_mode": self.processing_mode.value,
            "canvas_width": self.canvas_width,
            "canvas_height": self.canvas_height,
            "anchor": self.anchor.value,
            "fit_scale": self.fit_scale,
            "target_engine_notes": self.target_engine_notes,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "VideoSpriteRequest":
        if not isinstance(value, dict):
            raise TypeError("VideoSpriteRequest payload must be an object")
        frame_counts = value.get("frame_counts")
        return cls(
            schema_version=int(value["schema_version"]),
            asset_id=_string(value["asset_id"], "asset_id"),
            prompt=_string(value["prompt"], "prompt"),
            output_dir=_string(value["output_dir"], "output_dir"),
            source_preference=None if value.get("source_preference") is None else VideoSourcePreference(value["source_preference"]),
            existing_video_path=None if value.get("existing_video_path") is None else _string(value["existing_video_path"], "existing_video_path"),
            provider=None if value.get("provider") is None else ExternalProvider(value["provider"]),
            backend=_optional_string(value.get("backend"), "backend"),
            region=_optional_string(value.get("region"), "region"),
            model=_optional_string(value.get("model"), "model"),
            action_name=_optional_string(value.get("action_name"), "action_name"),
            generation_mode=VideoGenerationMode(value.get("generation_mode", "t2v")),
            first_frame_path=None if value.get("first_frame_path") is None else _string(value["first_frame_path"], "first_frame_path"),
            last_frame_path=None if value.get("last_frame_path") is None else _string(value["last_frame_path"], "last_frame_path"),
            reference_paths=tuple(_string(item, "reference_paths") for item in value.get("reference_paths", [])),
            loop=value.get("loop", True),
            clip_start_seconds=value.get("clip_start_seconds", 0.0),
            clip_end_seconds=value.get("clip_end_seconds"),
            frame_counts=(24,) if frame_counts is None else tuple(frame_counts),
            outputs=tuple(VideoOutput(item) for item in value.get("outputs", ["frames", "sheets", "gif"])),
            background_mode=VideoBackgroundMode(value.get("background_mode", "rembg")),
            chroma_color=value.get("chroma_color"),
            rembg_refinement=value.get("rembg_refinement"),
            processing_mode=VideoProcessingMode(value.get("processing_mode", "hd")),
            canvas_width=value.get("canvas_width"),
            canvas_height=value.get("canvas_height"),
            anchor=VideoAnchor(value.get("anchor", "feet")),
            fit_scale=value.get("fit_scale", 0.88),
            target_engine_notes=_optional_string(value.get("target_engine_notes"), "target_engine_notes"),
        )


@dataclass(frozen=True)
class VideoSourceDecision:
    schema_version: int
    request_fingerprint: str
    source_preference: VideoSourcePreference | None
    provider: ExternalProvider | None
    backend: str | None
    requires_user_selection: bool
    requires_paid_confirmation: bool
    reason: str

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        _digest(self.request_fingerprint, "request_fingerprint")
        if self.source_preference is not None and not isinstance(self.source_preference, VideoSourcePreference):
            raise TypeError("source_preference must be VideoSourcePreference")
        if self.provider is not None and not isinstance(self.provider, ExternalProvider):
            raise TypeError("provider must be ExternalProvider")
        if not isinstance(self.requires_user_selection, bool) or not isinstance(self.requires_paid_confirmation, bool):
            raise TypeError("selection and confirmation flags must be booleans")
        _string(self.reason, "reason")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "request_fingerprint": self.request_fingerprint,
            "source_preference": None if self.source_preference is None else self.source_preference.value,
            "provider": None if self.provider is None else self.provider.value,
            "backend": self.backend,
            "requires_user_selection": self.requires_user_selection,
            "requires_paid_confirmation": self.requires_paid_confirmation,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "VideoSourceDecision":
        return cls(
            schema_version=int(value["schema_version"]),
            request_fingerprint=_digest(value["request_fingerprint"], "request_fingerprint"),
            source_preference=None if value.get("source_preference") is None else VideoSourcePreference(value["source_preference"]),
            provider=None if value.get("provider") is None else ExternalProvider(value["provider"]),
            backend=value.get("backend"),
            requires_user_selection=bool(value["requires_user_selection"]),
            requires_paid_confirmation=bool(value["requires_paid_confirmation"]),
            reason=_string(value["reason"], "reason"),
        )


@dataclass(frozen=True)
class VideoSourceRecord:
    schema_version: int
    path: str
    sha256: str
    container: str
    video_codec: str
    width: int
    height: int
    display_rotation: int
    duration_seconds: float
    average_frame_rate: str | None
    real_frame_rate: str | None
    variable_frame_rate: bool
    frame_count: int | None
    audio_present: bool
    request_fingerprint: str
    provider: ExternalProvider | None = None
    backend: str | None = None
    model: str | None = None

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        object.__setattr__(self, "path", normalize_repo_relative_path(self.path, field_name="path"))
        _digest(self.sha256, "sha256")
        _string(self.container, "container")
        _string(self.video_codec, "video_codec")
        _positive_int(self.width, "width")
        _positive_int(self.height, "height")
        if self.display_rotation not in {0, 90, 180, 270}:
            raise ValueError("display_rotation must be 0, 90, 180, or 270")
        if not isinstance(self.duration_seconds, (int, float)) or self.duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")
        _digest(self.request_fingerprint, "request_fingerprint")
        if self.frame_count is not None:
            _positive_int(self.frame_count, "frame_count")
        if not isinstance(self.variable_frame_rate, bool) or not isinstance(self.audio_present, bool):
            raise TypeError("media flags must be booleans")

    def to_dict(self) -> dict[str, Any]:
        return {key: getattr(self, key) for key in (
            "schema_version", "path", "sha256", "container", "video_codec", "width", "height",
            "display_rotation", "duration_seconds", "average_frame_rate", "real_frame_rate",
            "variable_frame_rate", "frame_count", "audio_present", "request_fingerprint",
        )} | {"provider": None if self.provider is None else self.provider.value, "backend": self.backend, "model": self.model}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "VideoSourceRecord":
        return cls(**{key: value[key] for key in (
            "schema_version", "path", "sha256", "container", "video_codec", "width", "height",
            "display_rotation", "duration_seconds", "average_frame_rate", "real_frame_rate",
            "variable_frame_rate", "frame_count", "audio_present", "request_fingerprint",
        )}, provider=None if value.get("provider") is None else ExternalProvider(value["provider"]), backend=value.get("backend"), model=value.get("model"))


@dataclass(frozen=True)
class VideoFrameRecord:
    schema_version: int
    output_index: int
    source_timestamp: float
    source_frame_index: int | None
    raw_path: str
    clean_path: str | None
    delivery_path: str | None
    sha256: str

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        if self.output_index < 0:
            raise ValueError("output_index must not be negative")
        if self.source_timestamp < 0:
            raise ValueError("source_timestamp must not be negative")
        for field in ("raw_path", "clean_path", "delivery_path"):
            value = getattr(self, field)
            if value is not None:
                object.__setattr__(self, field, normalize_repo_relative_path(value, field_name=field))
        _digest(self.sha256, "sha256")

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": 1, "output_index": self.output_index, "source_timestamp": self.source_timestamp, "source_frame_index": self.source_frame_index, "raw_path": self.raw_path, "clean_path": self.clean_path, "delivery_path": self.delivery_path, "sha256": self.sha256}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "VideoFrameRecord":
        return cls(**value)


@dataclass(frozen=True)
class VideoProcessingResult:
    schema_version: int
    asset_id: str
    request_fingerprint: str
    staging_dir: str
    frame_records: tuple[VideoFrameRecord, ...]
    artifacts: dict[str, str]
    timing_path: str
    diagnostics: tuple[str, ...] = ()
    needs_attention: bool = False
    attention_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        _string(self.asset_id, "asset_id")
        _digest(self.request_fingerprint, "request_fingerprint")
        object.__setattr__(self, "staging_dir", normalize_repo_relative_path(self.staging_dir, field_name="staging_dir"))
        object.__setattr__(self, "timing_path", normalize_repo_relative_path(self.timing_path, field_name="timing_path"))
        if not isinstance(self.needs_attention, bool):
            raise TypeError("needs_attention must be a boolean")

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": 1, "asset_id": self.asset_id, "request_fingerprint": self.request_fingerprint, "staging_dir": self.staging_dir, "frame_records": [item.to_dict() for item in self.frame_records], "artifacts": dict(self.artifacts), "timing_path": self.timing_path, "diagnostics": list(self.diagnostics), "needs_attention": self.needs_attention, "attention_reasons": list(self.attention_reasons)}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "VideoProcessingResult":
        return cls(schema_version=int(value["schema_version"]), asset_id=str(value["asset_id"]), request_fingerprint=str(value["request_fingerprint"]), staging_dir=str(value["staging_dir"]), frame_records=tuple(VideoFrameRecord.from_dict(item) for item in value.get("frame_records", [])), artifacts={str(key): str(path) for key, path in value.get("artifacts", {}).items()}, timing_path=str(value["timing_path"]), diagnostics=tuple(str(item) for item in value.get("diagnostics", [])), needs_attention=bool(value.get("needs_attention", False)), attention_reasons=tuple(str(item) for item in value.get("attention_reasons", [])))
