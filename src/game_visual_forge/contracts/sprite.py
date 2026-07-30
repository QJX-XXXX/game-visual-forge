from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, TypeVar

from .pathing import normalize_repo_relative_path
from .provider import ExternalProvider


_DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}")
_HEX_COLOR_PATTERN = re.compile(r"#[0-9a-fA-F]{6}")
_EnumT = TypeVar("_EnumT", bound=StrEnum)


def _require_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")
    return value


def _require_optional_string(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_string(value, field_name)


def _require_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")
    return value


def _require_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{field_name} must be a boolean")
    return value


def _require_schema_version(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("schema_version must be an integer")
    if value != 1:
        raise ValueError("schema_version must be 1")
    return value


def _require_string_sequence(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or isinstance(value, str):
        raise TypeError(f"{field_name} must be a list of strings")
    return tuple(_require_string(item, field_name) for item in value)


def _require_enum(value: Any, enum_type: type[_EnumT], field_name: str) -> _EnumT:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    try:
        return enum_type(value)
    except ValueError as error:
        raise ValueError(f"unsupported {field_name}: {value}") from error


def _require_digest(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not _DIGEST_PATTERN.fullmatch(value):
        raise ValueError(f"{field_name} must be a SHA-256 hex digest")
    return value


class SpriteSourcePreference(StrEnum):
    AUTO = "auto"
    AGENT_NATIVE = "agent-native"
    DREAMINA = "dreamina"
    WANXIANG = "wanxiang"
    LOCAL_TOOL = "local-tool"
    EXISTING_FILE = "existing-file"


class SourceType(StrEnum):
    AGENT_NATIVE = "agent-native"
    DREAMINA = "dreamina"
    WANXIANG = "wanxiang"
    LOCAL_TOOL = "local-tool"
    EXISTING_FILE = "existing-file"


class SpriteLayout(StrEnum):
    GRID = "grid"
    STRIP = "strip"


class SpriteOutput(StrEnum):
    FRAMES = "frames"
    SHEET = "sheet"
    GIF = "gif"


class BackgroundRemoval(StrEnum):
    REMBG = "rembg"
    CHROMA = "chroma"
    PRESERVE = "preserve"


@dataclass(frozen=True)
class SpriteRequest:
    schema_version: int
    asset_id: str
    prompt: str
    output_dir: str
    source_preference: SpriteSourcePreference
    canvas_width: int
    canvas_height: int
    layout: SpriteLayout
    frame_count: int
    directions: tuple[str, ...]
    outputs: tuple[SpriteOutput, ...]
    reference_paths: tuple[str, ...] = ()
    style_constraints: tuple[str, ...] = ()
    identity_constraints: tuple[str, ...] = ()
    action_name: str | None = None
    frame_width: int | None = None
    frame_height: int | None = None
    grid_rows: int = 1
    grid_columns: int = 1
    background_removal: BackgroundRemoval = BackgroundRemoval.PRESERVE
    chroma_color: str | None = None
    target_engine_notes: str | None = None

    def __post_init__(self) -> None:
        _require_schema_version(self.schema_version)
        _require_string(self.asset_id, "asset_id")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", self.asset_id):
            raise ValueError("asset_id must be a lowercase slug")
        _require_string(self.prompt, "prompt")
        object.__setattr__(
            self,
            "output_dir",
            normalize_repo_relative_path(self.output_dir, field_name="output_dir"),
        )
        object.__setattr__(
            self,
            "reference_paths",
            tuple(
                normalize_repo_relative_path(path, field_name="reference_paths")
                for path in _require_string_sequence(self.reference_paths, "reference_paths")
            ),
        )
        object.__setattr__(self, "style_constraints", _require_string_sequence(self.style_constraints, "style_constraints"))
        object.__setattr__(self, "identity_constraints", _require_string_sequence(self.identity_constraints, "identity_constraints"))
        object.__setattr__(self, "directions", _require_string_sequence(self.directions, "directions"))
        if not self.directions:
            raise ValueError("directions must not be empty")
        if not self.outputs:
            raise ValueError("outputs must not be empty")
        if not all(isinstance(item, SpriteOutput) for item in self.outputs):
            raise TypeError("outputs must contain SpriteOutput values")
        _require_int(self.canvas_width, "canvas_width")
        _require_int(self.canvas_height, "canvas_height")
        _require_int(self.frame_count, "frame_count")
        _require_int(self.grid_rows, "grid_rows")
        _require_int(self.grid_columns, "grid_columns")
        if self.grid_rows * self.grid_columns < self.frame_count:
            raise ValueError("grid capacity must cover frame_count")
        if self.frame_count % len(self.directions) != 0:
            raise ValueError("frame_count must divide evenly across directions")
        if self.layout is SpriteLayout.STRIP and self.grid_rows != 1:
            raise ValueError("strip layout requires grid_rows = 1")
        if (self.frame_width is None) != (self.frame_height is None):
            raise ValueError("frame_width and frame_height must be provided together")
        if self.frame_width is not None:
            _require_int(self.frame_width, "frame_width")
            _require_int(self.frame_height, "frame_height")
        if not isinstance(self.background_removal, BackgroundRemoval):
            raise TypeError("background_removal must be BackgroundRemoval")
        if self.background_removal is BackgroundRemoval.CHROMA:
            if self.chroma_color is None or not _HEX_COLOR_PATTERN.fullmatch(self.chroma_color):
                raise ValueError("chroma_color must be an RGB hex color")
        elif self.chroma_color is not None:
            raise ValueError("chroma_color is only valid for chroma removal")
        _require_optional_string(self.action_name, "action_name")
        _require_optional_string(self.target_engine_notes, "target_engine_notes")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "asset_id": self.asset_id,
            "prompt": self.prompt,
            "output_dir": self.output_dir,
            "source_preference": self.source_preference.value,
            "canvas_width": self.canvas_width,
            "canvas_height": self.canvas_height,
            "layout": self.layout.value,
            "frame_count": self.frame_count,
            "directions": list(self.directions),
            "outputs": [item.value for item in self.outputs],
            "reference_paths": list(self.reference_paths),
            "style_constraints": list(self.style_constraints),
            "identity_constraints": list(self.identity_constraints),
            "action_name": self.action_name,
            "frame_width": self.frame_width,
            "frame_height": self.frame_height,
            "grid_rows": self.grid_rows,
            "grid_columns": self.grid_columns,
            "background_removal": self.background_removal.value,
            "chroma_color": self.chroma_color,
            "target_engine_notes": self.target_engine_notes,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SpriteRequest":
        if not isinstance(value, dict):
            raise TypeError("SpriteRequest payload must be an object")
        directions = value["directions"]
        outputs = value["outputs"]
        if not isinstance(directions, list):
            raise TypeError("directions must be a JSON array")
        if not isinstance(outputs, list):
            raise TypeError("outputs must be a JSON array")
        return cls(
            schema_version=_require_schema_version(value["schema_version"]),
            asset_id=_require_string(value["asset_id"], "asset_id"),
            prompt=_require_string(value["prompt"], "prompt"),
            output_dir=_require_string(value["output_dir"], "output_dir"),
            source_preference=_require_enum(value["source_preference"], SpriteSourcePreference, "source_preference"),
            canvas_width=_require_int(value["canvas_width"], "canvas_width"),
            canvas_height=_require_int(value["canvas_height"], "canvas_height"),
            layout=_require_enum(value["layout"], SpriteLayout, "layout"),
            frame_count=_require_int(value["frame_count"], "frame_count"),
            directions=tuple(_require_string(item, "directions") for item in directions),
            outputs=tuple(_require_enum(item, SpriteOutput, "outputs[]") for item in outputs),
            reference_paths=tuple(_require_string(item, "reference_paths") for item in value.get("reference_paths", [])),
            style_constraints=tuple(_require_string(item, "style_constraints") for item in value.get("style_constraints", [])),
            identity_constraints=tuple(_require_string(item, "identity_constraints") for item in value.get("identity_constraints", [])),
            action_name=_require_optional_string(value.get("action_name"), "action_name"),
            frame_width=(None if value.get("frame_width") is None else _require_int(value["frame_width"], "frame_width")),
            frame_height=(None if value.get("frame_height") is None else _require_int(value["frame_height"], "frame_height")),
            grid_rows=_require_int(value["grid_rows"], "grid_rows"),
            grid_columns=_require_int(value["grid_columns"], "grid_columns"),
            background_removal=_require_enum(value["background_removal"], BackgroundRemoval, "background_removal"),
            chroma_color=_require_optional_string(value.get("chroma_color"), "chroma_color"),
            target_engine_notes=_require_optional_string(value.get("target_engine_notes"), "target_engine_notes"),
        )


@dataclass(frozen=True)
class SourceDecision:
    schema_version: int
    source_type: SourceType | None
    requires_user_selection: bool
    requires_paid_confirmation: bool
    reason: str
    request_fingerprint: str
    selected_provider: ExternalProvider | None = None

    def __post_init__(self) -> None:
        _require_schema_version(self.schema_version)
        _require_bool(self.requires_user_selection, "requires_user_selection")
        _require_bool(self.requires_paid_confirmation, "requires_paid_confirmation")
        _require_string(self.reason, "reason")
        _require_digest(self.request_fingerprint, "request_fingerprint")
        if self.source_type in {SourceType.DREAMINA, SourceType.WANXIANG} and self.selected_provider is None:
            raise ValueError("provider source requires selected_provider")
        if self.requires_paid_confirmation and self.source_type not in {SourceType.DREAMINA, SourceType.WANXIANG}:
            raise ValueError("paid confirmation requires a provider source")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "source_type": self.source_type.value if self.source_type else None,
            "requires_user_selection": self.requires_user_selection,
            "requires_paid_confirmation": self.requires_paid_confirmation,
            "reason": self.reason,
            "request_fingerprint": self.request_fingerprint,
            "selected_provider": self.selected_provider.value if self.selected_provider else None,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SourceDecision":
        if not isinstance(value, dict):
            raise TypeError("SourceDecision payload must be an object")
        return cls(
            schema_version=_require_schema_version(value["schema_version"]),
            source_type=None if value.get("source_type") is None else _require_enum(value["source_type"], SourceType, "source_type"),
            requires_user_selection=_require_bool(value["requires_user_selection"], "requires_user_selection"),
            requires_paid_confirmation=_require_bool(value["requires_paid_confirmation"], "requires_paid_confirmation"),
            reason=_require_string(value["reason"], "reason"),
            request_fingerprint=_require_digest(value["request_fingerprint"], "request_fingerprint"),
            selected_provider=None if value.get("selected_provider") is None else _require_enum(value["selected_provider"], ExternalProvider, "selected_provider"),
        )


@dataclass(frozen=True)
class PromptPackage:
    schema_version: int
    positive_prompt: str
    negative_constraints: tuple[str, ...]
    reference_paths: tuple[str, ...]
    canvas_width: int
    canvas_height: int
    grid_rows: int
    grid_columns: int
    frame_order: tuple[str, ...]
    solid_background: str | None
    expected_output_path: str

    def __post_init__(self) -> None:
        _require_schema_version(self.schema_version)
        _require_string(self.positive_prompt, "positive_prompt")
        _require_string_sequence(self.negative_constraints, "negative_constraints")
        object.__setattr__(self, "reference_paths", tuple(normalize_repo_relative_path(path, field_name="reference_paths") for path in self.reference_paths))
        _require_int(self.canvas_width, "canvas_width")
        _require_int(self.canvas_height, "canvas_height")
        _require_int(self.grid_rows, "grid_rows")
        _require_int(self.grid_columns, "grid_columns")
        _require_string_sequence(self.frame_order, "frame_order")
        if self.solid_background is not None and not _HEX_COLOR_PATTERN.fullmatch(self.solid_background):
            raise ValueError("solid_background must be an RGB hex color")
        object.__setattr__(self, "expected_output_path", normalize_repo_relative_path(self.expected_output_path, field_name="expected_output_path"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "positive_prompt": self.positive_prompt,
            "negative_constraints": list(self.negative_constraints),
            "reference_paths": list(self.reference_paths),
            "canvas_width": self.canvas_width,
            "canvas_height": self.canvas_height,
            "grid_rows": self.grid_rows,
            "grid_columns": self.grid_columns,
            "frame_order": list(self.frame_order),
            "solid_background": self.solid_background,
            "expected_output_path": self.expected_output_path,
        }


@dataclass(frozen=True)
class RawImageRecord:
    schema_version: int
    path: str
    sha256: str
    width: int
    height: int
    media_format: str
    source_type: SourceType
    request_fingerprint: str
    provider: ExternalProvider | None = None
    model: str | None = None

    def __post_init__(self) -> None:
        _require_schema_version(self.schema_version)
        object.__setattr__(self, "path", normalize_repo_relative_path(self.path, field_name="path"))
        _require_digest(self.sha256, "sha256")
        _require_int(self.width, "width")
        _require_int(self.height, "height")
        _require_string(self.media_format, "media_format")
        _require_digest(self.request_fingerprint, "request_fingerprint")
        if not isinstance(self.source_type, SourceType):
            raise TypeError("source_type must be SourceType")
        if self.provider is not None and not isinstance(self.provider, ExternalProvider):
            raise TypeError("provider must be ExternalProvider")
        _require_optional_string(self.model, "model")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "path": self.path,
            "sha256": self.sha256,
            "width": self.width,
            "height": self.height,
            "media_format": self.media_format,
            "source_type": self.source_type.value,
            "request_fingerprint": self.request_fingerprint,
            "provider": self.provider.value if self.provider else None,
            "model": self.model,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RawImageRecord":
        if not isinstance(value, dict):
            raise TypeError("RawImageRecord payload must be an object")
        return cls(
            schema_version=_require_schema_version(value["schema_version"]),
            path=_require_string(value["path"], "path"),
            sha256=_require_digest(value["sha256"], "sha256"),
            width=_require_int(value["width"], "width"),
            height=_require_int(value["height"], "height"),
            media_format=_require_string(value["media_format"], "media_format"),
            source_type=_require_enum(value["source_type"], SourceType, "source_type"),
            request_fingerprint=_require_digest(value["request_fingerprint"], "request_fingerprint"),
            provider=None if value.get("provider") is None else _require_enum(value["provider"], ExternalProvider, "provider"),
            model=_require_optional_string(value.get("model"), "model"),
        )
