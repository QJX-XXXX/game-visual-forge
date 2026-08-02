from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .asset import SourcePreference
from .pathing import normalize_repo_relative_path
from .provider import ExternalProvider


_SLUG_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")


def _positive_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _coordinate(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return value


def _string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must not be empty")
    return value


class MapShapeType(StrEnum):
    RECT = "rect"
    CIRCLE = "circle"
    ELLIPSE = "ellipse"
    POLYGON = "polygon"


class MapSourceType(StrEnum):
    AGENT_NATIVE = "agent-native"
    JIMENG = "jimeng"
    WANXIANG = "wanxiang"
    LOCAL_TOOL = "local-tool"
    EXISTING_FILE = "existing-file"


@dataclass(frozen=True)
class MapPoint:
    x: int
    y: int

    def __post_init__(self) -> None:
        _coordinate(self.x, "x")
        _coordinate(self.y, "y")

    def to_dict(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "MapPoint":
        return cls(_coordinate(value["x"], "x"), _coordinate(value["y"], "y"))


@dataclass(frozen=True)
class MapShape:
    shape_id: str
    shape_type: MapShapeType
    x: int = 0
    y: int = 0
    width: int | None = None
    height: int | None = None
    radius: int | None = None
    radius_x: int | None = None
    radius_y: int | None = None
    points: tuple[MapPoint, ...] = ()

    def __post_init__(self) -> None:
        if not _SLUG_PATTERN.fullmatch(self.shape_id):
            raise ValueError("shape_id must be a lowercase slug")
        if not isinstance(self.shape_type, MapShapeType):
            raise TypeError("shape_type must be MapShapeType")
        _coordinate(self.x, "x")
        _coordinate(self.y, "y")
        if self.shape_type is MapShapeType.RECT:
            if self.width is None or self.height is None:
                raise ValueError("rect requires width and height")
            _positive_int(self.width, "width")
            _positive_int(self.height, "height")
        elif self.shape_type is MapShapeType.CIRCLE:
            if self.radius is None:
                raise ValueError("circle requires radius")
            _positive_int(self.radius, "radius")
        elif self.shape_type is MapShapeType.ELLIPSE:
            if self.radius_x is None or self.radius_y is None:
                raise ValueError("ellipse requires radius_x and radius_y")
            _positive_int(self.radius_x, "radius_x")
            _positive_int(self.radius_y, "radius_y")
        else:
            if len(self.points) < 3 or not all(isinstance(point, MapPoint) for point in self.points):
                raise ValueError("polygon requires at least three points")

    def bounds(self) -> tuple[int, int, int, int]:
        if self.shape_type is MapShapeType.RECT:
            assert self.width is not None and self.height is not None
            return self.x, self.y, self.x + self.width, self.y + self.height
        if self.shape_type is MapShapeType.CIRCLE:
            assert self.radius is not None
            return self.x - self.radius, self.y - self.radius, self.x + self.radius, self.y + self.radius
        if self.shape_type is MapShapeType.ELLIPSE:
            assert self.radius_x is not None and self.radius_y is not None
            return self.x - self.radius_x, self.y - self.radius_y, self.x + self.radius_x, self.y + self.radius_y
        return (
            min(point.x for point in self.points),
            min(point.y for point in self.points),
            max(point.x for point in self.points),
            max(point.y for point in self.points),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.shape_id,
            "type": self.shape_type.value,
            "x": self.x,
            "y": self.y,
        }
        if self.width is not None:
            payload["w"] = self.width
        if self.height is not None:
            payload["h"] = self.height
        if self.radius is not None:
            payload["radius"] = self.radius
        if self.radius_x is not None:
            payload["rx"] = self.radius_x
        if self.radius_y is not None:
            payload["ry"] = self.radius_y
        if self.points:
            payload["points"] = [point.to_dict() for point in self.points]
        return payload

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "MapShape":
        return cls(
            shape_id=_string(value["id"], "id"),
            shape_type=MapShapeType(value["type"]),
            x=_coordinate(value.get("x", 0), "x"),
            y=_coordinate(value.get("y", 0), "y"),
            width=None if value.get("w") is None else _positive_int(value["w"], "w"),
            height=None if value.get("h") is None else _positive_int(value["h"], "h"),
            radius=None if value.get("radius") is None else _positive_int(value["radius"], "radius"),
            radius_x=None if value.get("rx") is None else _positive_int(value["rx"], "rx"),
            radius_y=None if value.get("ry") is None else _positive_int(value["ry"], "ry"),
            points=tuple(MapPoint.from_dict(item) for item in value.get("points", [])),
        )


def _shape_sequence(value: Any, field_name: str) -> tuple[MapShape, ...]:
    if not isinstance(value, list):
        raise TypeError(f"{field_name} must be a JSON array")
    return tuple(MapShape.from_dict(item) for item in value)


@dataclass(frozen=True)
class MapRequest:
    schema_version: int
    asset_id: str
    prompt: str
    output_dir: str
    source_preference: SourcePreference
    canvas_width: int
    canvas_height: int
    spawn: MapPoint
    walk_bounds: tuple[MapShape, ...]
    blockers: tuple[MapShape, ...] = ()
    zones: tuple[MapShape, ...] = ()
    map_mode: str = "scene_mode"
    perspective: str = "top-down"
    reference_paths: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        if not _SLUG_PATTERN.fullmatch(self.asset_id):
            raise ValueError("asset_id must be a lowercase slug")
        _string(self.prompt, "prompt")
        object.__setattr__(self, "output_dir", normalize_repo_relative_path(self.output_dir, field_name="output_dir"))
        _positive_int(self.canvas_width, "canvas_width")
        _positive_int(self.canvas_height, "canvas_height")
        if not isinstance(self.source_preference, SourcePreference):
            raise TypeError("source_preference must be SourcePreference")
        if not isinstance(self.spawn, MapPoint):
            raise TypeError("spawn must be MapPoint")
        if not self.walk_bounds:
            raise ValueError("walk_bounds must not be empty")
        for field_name, shapes in (("walk_bounds", self.walk_bounds), ("blockers", self.blockers), ("zones", self.zones)):
            if not isinstance(shapes, tuple) or not all(isinstance(shape, MapShape) for shape in shapes):
                raise TypeError(f"{field_name} must contain MapShape objects")
            ids = [shape.shape_id for shape in shapes]
            if len(ids) != len(set(ids)):
                raise ValueError(f"{field_name} shape ids must be unique")
            for shape in shapes:
                left, top, right, bottom = shape.bounds()
                if left < 0 or top < 0 or right > self.canvas_width or bottom > self.canvas_height:
                    raise ValueError(f"{field_name} shape is outside the map canvas: {shape.shape_id}")
        if self.spawn.x >= self.canvas_width or self.spawn.y >= self.canvas_height:
            raise ValueError("spawn must be inside the map canvas")
        _string(self.map_mode, "map_mode")
        _string(self.perspective, "perspective")
        object.__setattr__(self, "reference_paths", tuple(normalize_repo_relative_path(path, field_name="reference_paths") for path in self.reference_paths))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "asset_id": self.asset_id,
            "prompt": self.prompt,
            "output_dir": self.output_dir,
            "source_preference": self.source_preference.value,
            "canvas_width": self.canvas_width,
            "canvas_height": self.canvas_height,
            "spawn": self.spawn.to_dict(),
            "walk_bounds": [shape.to_dict() for shape in self.walk_bounds],
            "blockers": [shape.to_dict() for shape in self.blockers],
            "zones": [shape.to_dict() for shape in self.zones],
            "map_mode": self.map_mode,
            "perspective": self.perspective,
            "reference_paths": list(self.reference_paths),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "MapRequest":
        return cls(
            schema_version=int(value["schema_version"]),
            asset_id=str(value["asset_id"]),
            prompt=str(value["prompt"]),
            output_dir=str(value["output_dir"]),
            source_preference=SourcePreference(value["source_preference"]),
            canvas_width=int(value["canvas_width"]),
            canvas_height=int(value["canvas_height"]),
            spawn=MapPoint.from_dict(value["spawn"]),
            walk_bounds=_shape_sequence(value["walk_bounds"], "walk_bounds"),
            blockers=_shape_sequence(value.get("blockers", []), "blockers"),
            zones=_shape_sequence(value.get("zones", []), "zones"),
            map_mode=str(value.get("map_mode", "scene_mode")),
            perspective=str(value.get("perspective", "top-down")),
            reference_paths=tuple(str(item) for item in value.get("reference_paths", [])),
        )


@dataclass(frozen=True)
class MapSourceCapabilities:
    supported: bool
    operations: tuple[str, ...]


@dataclass(frozen=True)
class MapSourceDecision:
    schema_version: int
    source_type: MapSourceType | None
    requires_user_selection: bool
    requires_paid_confirmation: bool
    reason: str
    request_fingerprint: str
    selected_provider: ExternalProvider | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "source_type": None if self.source_type is None else self.source_type.value,
            "requires_user_selection": self.requires_user_selection,
            "requires_paid_confirmation": self.requires_paid_confirmation,
            "reason": self.reason,
            "request_fingerprint": self.request_fingerprint,
            "selected_provider": None if self.selected_provider is None else self.selected_provider.value,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "MapSourceDecision":
        return cls(
            schema_version=value["schema_version"],
            source_type=None if value.get("source_type") is None else MapSourceType(value["source_type"]),
            requires_user_selection=value["requires_user_selection"],
            requires_paid_confirmation=value["requires_paid_confirmation"],
            reason=value["reason"],
            request_fingerprint=value["request_fingerprint"],
            selected_provider=None if value.get("selected_provider") is None else ExternalProvider(value["selected_provider"]),
        )
