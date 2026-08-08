from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


_SLUG = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")


def _slug(value: str, field: str) -> str:
    if not isinstance(value, str) or not _SLUG.fullmatch(value):
        raise ValueError(f"{field} must be a lowercase slug")
    return value


def _non_negative(value: int, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _positive(value: int, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


class TileObjectKind(StrEnum):
    BUILDING = "building"
    PROP = "prop"


class EntranceConnectionTarget(StrEnum):
    WALKABLE = "walkable"
    ROAD = "road"


class RoadConnectivityPolicy(StrEnum):
    REQUIRED = "required"
    PARTIAL = "partial"
    NONE = "none"


class TileMapApprovalWorkflow(StrEnum):
    LEGACY_VISUAL = "legacy_visual"
    TWO_GATE = "two_gate"


@dataclass(frozen=True)
class GridCell:
    x: int
    y: int

    def __post_init__(self) -> None:
        _non_negative(self.x, "x")
        _non_negative(self.y, "y")

    def to_dict(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "GridCell":
        return cls(int(value["x"]), int(value["y"]))


@dataclass(frozen=True)
class GridRect:
    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        _non_negative(self.x, "x")
        _non_negative(self.y, "y")
        _positive(self.width, "width")
        _positive(self.height, "height")

    def contains(self, cell: GridCell) -> bool:
        return self.x <= cell.x < self.x + self.width and self.y <= cell.y < self.y + self.height

    def to_dict(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "GridRect":
        return cls(int(value["x"]), int(value["y"]), int(value["width"]), int(value["height"]))


@dataclass(frozen=True)
class RoadConnectionRequirement:
    rule_id: str
    start: GridCell
    end: GridCell

    def __post_init__(self) -> None:
        _slug(self.rule_id, "rule_id")

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.rule_id, "start": self.start.to_dict(), "end": self.end.to_dict()}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RoadConnectionRequirement":
        return cls(str(value.get("id", value.get("rule_id"))), GridCell.from_dict(value["start"]), GridCell.from_dict(value["end"]))


@dataclass(frozen=True)
class TileObjectAssetDefinition:
    asset_id: str
    kind: TileObjectKind
    prompt: str
    pixel_width: int
    pixel_height: int
    pixels_per_unit: int
    anchor_x: int
    anchor_y: int
    footprint: GridRect
    collision_cells: tuple[GridCell, ...]
    doorway_cell: GridCell | None
    max_instances: int
    max_adjacent: int

    def __post_init__(self) -> None:
        _slug(self.asset_id, "asset_id")
        if isinstance(self.kind, str):
            object.__setattr__(self, "kind", TileObjectKind(self.kind))
        elif not isinstance(self.kind, TileObjectKind):
            raise TypeError("kind must be TileObjectKind")
        if not isinstance(self.prompt, str) or not self.prompt.strip():
            raise ValueError("prompt must not be empty")
        for field in ("pixel_width", "pixel_height", "pixels_per_unit"):
            _positive(getattr(self, field), field)
        for field in ("anchor_x", "anchor_y"):
            _non_negative(getattr(self, field), field)
        if self.anchor_x >= self.footprint.width or self.anchor_y >= self.footprint.height:
            raise ValueError("anchor must be inside footprint")
        cells = tuple(self.collision_cells)
        if len(set(cells)) != len(cells):
            raise ValueError("collision_cells must be unique")
        if any(not self.footprint.contains(cell) for cell in cells):
            raise ValueError("collision_cells must be inside footprint")
        if self.doorway_cell is not None:
            if self.kind is not TileObjectKind.BUILDING:
                raise ValueError("only buildings may declare doorway_cell")
            if not self.footprint.contains(self.doorway_cell):
                raise ValueError("doorway_cell must be inside footprint")
            if self.doorway_cell in cells:
                raise ValueError("doorway_cell must not be collidable")
        elif self.kind is TileObjectKind.BUILDING:
            raise ValueError("building assets require doorway_cell")
        _non_negative(self.max_instances, "max_instances")
        _non_negative(self.max_adjacent, "max_adjacent")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.asset_id, "kind": self.kind.value, "prompt": self.prompt,
            "pixel_width": self.pixel_width, "pixel_height": self.pixel_height,
            "pixels_per_unit": self.pixels_per_unit, "anchor": {"x": self.anchor_x, "y": self.anchor_y},
            "footprint": self.footprint.to_dict(), "collision_cells": [cell.to_dict() for cell in self.collision_cells],
            "doorway_cell": None if self.doorway_cell is None else self.doorway_cell.to_dict(),
            "max_instances": self.max_instances, "max_adjacent": self.max_adjacent,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TileObjectAssetDefinition":
        anchor = value["anchor"]
        return cls(
            str(value["id"]), TileObjectKind(value["kind"]), str(value["prompt"]), int(value["pixel_width"]),
            int(value["pixel_height"]), int(value["pixels_per_unit"]), int(anchor["x"]), int(anchor["y"]),
            GridRect.from_dict(value["footprint"]), tuple(GridCell.from_dict(item) for item in value.get("collision_cells", [])),
            None if value.get("doorway_cell") is None else GridCell.from_dict(value["doorway_cell"]),
            int(value.get("max_instances", 0)), int(value.get("max_adjacent", 0)),
        )


@dataclass(frozen=True)
class TileObjectPlacement:
    instance_id: str
    asset_id: str
    x: int
    y: int
    sorting_order: int

    def __post_init__(self) -> None:
        _slug(self.instance_id, "instance_id")
        _slug(self.asset_id, "asset_id")
        _non_negative(self.x, "x")
        _non_negative(self.y, "y")
        if isinstance(self.sorting_order, bool) or not isinstance(self.sorting_order, int):
            raise ValueError("sorting_order must be an integer")

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.instance_id, "asset_id": self.asset_id, "x": self.x, "y": self.y, "sorting_order": self.sorting_order}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TileObjectPlacement":
        return cls(str(value["id"]), str(value["asset_id"]), int(value["x"]), int(value["y"]), int(value.get("sorting_order", 0)))


@dataclass(frozen=True)
class TileObjectEntrance:
    entrance_id: str
    instance_id: str
    connection_target: EntranceConnectionTarget
    target_scene_id: str
    target_spawn_id: str

    def __post_init__(self) -> None:
        _slug(self.entrance_id, "entrance_id")
        _slug(self.instance_id, "instance_id")
        if isinstance(self.connection_target, str):
            object.__setattr__(self, "connection_target", EntranceConnectionTarget(self.connection_target))
        elif not isinstance(self.connection_target, EntranceConnectionTarget):
            raise TypeError("connection_target must be EntranceConnectionTarget")
        if not isinstance(self.target_scene_id, str) or not self.target_scene_id.strip() or "\\" in self.target_scene_id or ".." in self.target_scene_id:
            raise ValueError("target_scene_id must be a safe forward-slash path")
        _slug(self.target_spawn_id, "target_spawn_id")

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.entrance_id, "instance_id": self.instance_id, "connection_target": self.connection_target.value, "target_scene_id": self.target_scene_id, "target_spawn_id": self.target_spawn_id}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TileObjectEntrance":
        return cls(str(value["id"]), str(value["instance_id"]), EntranceConnectionTarget(value["connection_target"]), str(value["target_scene_id"]), str(value["target_spawn_id"]))
