from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .pathing import normalize_repo_relative_path


_SLUG_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")


class AssetKind(StrEnum):
    SPRITE = "sprite"
    MAP = "map"
    VIDEO_SPRITE = "video-sprite"


class SourcePreference(StrEnum):
    AUTO = "auto"
    AGENT_NATIVE = "agent-native"
    JIMENG = "jimeng"
    WANXIANG = "wanxiang"
    EXISTING_FILE = "existing-file"

@dataclass(frozen=True)
class AssetBrief:
    schema_version: int
    asset_id: str
    kind: AssetKind
    prompt: str
    output_dir: str
    source_preference: SourcePreference
    reference_paths: tuple[str, ...] = ()
    canvas_width: int | None = None
    canvas_height: int | None = None
    frame_count: int | None = None

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        if not _SLUG_PATTERN.fullmatch(self.asset_id):
            raise ValueError("asset_id must be a lowercase slug")
        if not self.prompt.strip():
            raise ValueError("prompt must not be empty")
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
                for path in self.reference_paths
            ),
        )
        for field_name in ("canvas_width", "canvas_height", "frame_count"):
            value = getattr(self, field_name)
            if value is not None and value <= 0:
                raise ValueError(f"{field_name} must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "asset_id": self.asset_id,
            "kind": self.kind.value,
            "prompt": self.prompt,
            "output_dir": self.output_dir,
            "source_preference": self.source_preference.value,
            "reference_paths": list(self.reference_paths),
            "canvas_width": self.canvas_width,
            "canvas_height": self.canvas_height,
            "frame_count": self.frame_count,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AssetBrief":
        return cls(
            schema_version=int(value["schema_version"]),
            asset_id=str(value["asset_id"]),
            kind=AssetKind(value["kind"]),
            prompt=str(value["prompt"]),
            output_dir=str(value["output_dir"]),
            source_preference=SourcePreference(value["source_preference"]),
            reference_paths=tuple(str(item) for item in value.get("reference_paths", [])),
            canvas_width=int(value["canvas_width"]) if value.get("canvas_width") is not None else None,
            canvas_height=int(value["canvas_height"]) if value.get("canvas_height") is not None else None,
            frame_count=int(value["frame_count"]) if value.get("frame_count") is not None else None,
        )
