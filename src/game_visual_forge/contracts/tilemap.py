from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .asset import SourcePreference
from .pathing import normalize_repo_relative_path


_SLUG_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")


def _positive_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _non_negative_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return value


def _non_empty(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must not be empty")
    return value


class TileColliderType(StrEnum):
    NONE = "none"
    GRID = "grid"
    SPRITE = "sprite"


class TileFilterMode(StrEnum):
    POINT = "point"
    BILINEAR = "bilinear"


class TilemapEngineTarget(StrEnum):
    UNITY_TILEMAP = "Unity_Tilemap"


class TileSetProfile(StrEnum):
    STANDARD_16 = "standard_16"
    ADAPTIVE_HD = "adaptive_hd"


class TileSemanticRole(StrEnum):
    UNSPECIFIED = "unspecified"
    TERRAIN = "terrain"
    TERRAIN_TRANSITION = "terrain-transition"
    ROAD = "road"
    WATER = "water"
    BRIDGE = "bridge"
    DECORATION = "decoration"
    PROP = "prop"


class TileDirection(StrEnum):
    NORTH = "north"
    EAST = "east"
    SOUTH = "south"
    WEST = "west"


@dataclass(frozen=True)
class AtlasPageDefinition:
    atlas_id: str
    columns: int
    rows: int
    tile_width: int
    tile_height: int
    prompt: str

    def __post_init__(self) -> None:
        if not _SLUG_PATTERN.fullmatch(self.atlas_id):
            raise ValueError("atlas_id must be a lowercase slug")
        for field_name in ("columns", "rows", "tile_width", "tile_height"):
            _positive_int(getattr(self, field_name), field_name)
        _non_empty(self.prompt, "prompt")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.atlas_id,
            "columns": self.columns,
            "rows": self.rows,
            "tile_width": self.tile_width,
            "tile_height": self.tile_height,
            "prompt": self.prompt,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AtlasPageDefinition":
        return cls(
            atlas_id=str(value["id"]),
            columns=int(value["columns"]),
            rows=int(value["rows"]),
            tile_width=int(value["tile_width"]),
            tile_height=int(value["tile_height"]),
            prompt=str(value["prompt"]),
        )


@dataclass(frozen=True)
class TileDefinition:
    tile_id: str
    atlas_column: int
    atlas_row: int
    collider_type: TileColliderType = TileColliderType.NONE
    atlas_id: str = "page-01"
    semantic_role: TileSemanticRole = TileSemanticRole.UNSPECIFIED

    def __post_init__(self) -> None:
        if not _SLUG_PATTERN.fullmatch(self.tile_id):
            raise ValueError("tile_id must be a lowercase slug")
        _non_negative_int(self.atlas_column, "atlas_column")
        _non_negative_int(self.atlas_row, "atlas_row")
        if not isinstance(self.collider_type, TileColliderType):
            raise TypeError("collider_type must be TileColliderType")
        if not _SLUG_PATTERN.fullmatch(self.atlas_id):
            raise ValueError("atlas_id must be a lowercase slug")
        if not isinstance(self.semantic_role, TileSemanticRole):
            raise TypeError("semantic_role must be TileSemanticRole")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.tile_id,
            "atlas_column": self.atlas_column,
            "atlas_row": self.atlas_row,
            "collider_type": self.collider_type.value,
            "atlas_id": self.atlas_id,
            "semantic_role": self.semantic_role.value,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TileDefinition":
        return cls(
            tile_id=str(value["id"]),
            atlas_column=_non_negative_int(value["atlas_column"], "atlas_column"),
            atlas_row=_non_negative_int(value["atlas_row"], "atlas_row"),
            collider_type=TileColliderType(value.get("collider_type", "none")),
            atlas_id=str(value.get("atlas_id", "page-01")),
            semantic_role=TileSemanticRole(value.get("semantic_role", "unspecified")),
        )


@dataclass(frozen=True)
class TileAdjacencyRule:
    tile_id: str
    direction: TileDirection
    allowed_neighbors: tuple[str, ...]

    def __post_init__(self) -> None:
        if not _SLUG_PATTERN.fullmatch(self.tile_id):
            raise ValueError("tile_id must be a lowercase slug")
        if not isinstance(self.direction, TileDirection):
            raise TypeError("direction must be TileDirection")
        if not self.allowed_neighbors or not all(_SLUG_PATTERN.fullmatch(item) for item in self.allowed_neighbors):
            raise ValueError("allowed_neighbors must contain lowercase slugs")
        if len(self.allowed_neighbors) != len(set(self.allowed_neighbors)):
            raise ValueError("allowed_neighbors must be unique")

    def to_dict(self) -> dict[str, Any]:
        return {
            "tile_id": self.tile_id,
            "direction": self.direction.value,
            "allowed_neighbors": list(self.allowed_neighbors),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TileAdjacencyRule":
        neighbors = value["allowed_neighbors"]
        if not isinstance(neighbors, list):
            raise TypeError("allowed_neighbors must be a JSON array")
        return cls(
            tile_id=str(value["tile_id"]),
            direction=TileDirection(value["direction"]),
            allowed_neighbors=tuple(str(item) for item in neighbors),
        )


@dataclass(frozen=True)
class TileLayer:
    layer_id: str
    sorting_order: int
    has_collider: bool
    cells: tuple[str | None, ...]

    def __post_init__(self) -> None:
        if not _SLUG_PATTERN.fullmatch(self.layer_id):
            raise ValueError("layer_id must be a lowercase slug")
        if isinstance(self.sorting_order, bool) or not isinstance(self.sorting_order, int):
            raise TypeError("sorting_order must be an integer")
        if not isinstance(self.has_collider, bool):
            raise TypeError("has_collider must be a boolean")
        if not isinstance(self.cells, tuple) or not all(item is None or isinstance(item, str) for item in self.cells):
            raise TypeError("cells must contain tile ids or null")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.layer_id,
            "sorting_order": self.sorting_order,
            "has_collider": self.has_collider,
            "cells": list(self.cells),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TileLayer":
        cells = value["cells"]
        if not isinstance(cells, list):
            raise TypeError("cells must be a JSON array")
        return cls(
            layer_id=str(value["id"]),
            sorting_order=int(value.get("sorting_order", 0)),
            has_collider=bool(value.get("has_collider", False)),
            cells=tuple(None if item is None else str(item) for item in cells),
        )


@dataclass(frozen=True)
class TileMapRequest:
    schema_version: int
    asset_id: str
    prompt: str
    output_dir: str
    source_preference: SourcePreference
    tile_width: int
    tile_height: int
    atlas_columns: int
    atlas_rows: int
    map_width: int
    map_height: int
    tiles: tuple[TileDefinition, ...]
    layers: tuple[TileLayer, ...]
    palette_name: str
    unity_generated_root: str
    pixels_per_unit: int = 32
    atlas_margin: int = 0
    atlas_spacing: int = 0
    filter_mode: TileFilterMode = TileFilterMode.POINT
    engine_target: TilemapEngineTarget = TilemapEngineTarget.UNITY_TILEMAP
    reference_paths: tuple[str, ...] = ()
    tileset_profile: TileSetProfile = TileSetProfile.STANDARD_16
    max_tile_count: int = 16
    atlas_pages: tuple[AtlasPageDefinition, ...] = ()
    adjacency_rules: tuple[TileAdjacencyRule, ...] = ()

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        if not _SLUG_PATTERN.fullmatch(self.asset_id):
            raise ValueError("asset_id must be a lowercase slug")
        _non_empty(self.prompt, "prompt")
        object.__setattr__(self, "output_dir", normalize_repo_relative_path(self.output_dir, field_name="output_dir"))
        for field_name in ("tile_width", "tile_height", "atlas_columns", "atlas_rows", "map_width", "map_height", "pixels_per_unit"):
            _positive_int(getattr(self, field_name), field_name)
        _non_negative_int(self.atlas_margin, "atlas_margin")
        _non_negative_int(self.atlas_spacing, "atlas_spacing")
        if not isinstance(self.source_preference, SourcePreference):
            raise TypeError("source_preference must be SourcePreference")
        if not isinstance(self.filter_mode, TileFilterMode):
            raise TypeError("filter_mode must be TileFilterMode")
        if self.engine_target is not TilemapEngineTarget.UNITY_TILEMAP:
            raise ValueError("engine_target must be Unity_Tilemap")
        if not isinstance(self.tileset_profile, TileSetProfile):
            raise TypeError("tileset_profile must be TileSetProfile")
        if not isinstance(self.atlas_pages, tuple) or not all(isinstance(page, AtlasPageDefinition) for page in self.atlas_pages):
            raise TypeError("atlas_pages must contain AtlasPageDefinition values")
        if not isinstance(self.adjacency_rules, tuple) or not all(isinstance(rule, TileAdjacencyRule) for rule in self.adjacency_rules):
            raise TypeError("adjacency_rules must contain TileAdjacencyRule values")
        _positive_int(self.max_tile_count, "max_tile_count")
        if self.max_tile_count not in {16, 32, 48}:
            raise ValueError("max_tile_count must be one of 16, 32, or 48")
        _non_empty(self.palette_name, "palette_name")
        if "/" in self.palette_name or "\\" in self.palette_name:
            raise ValueError("palette_name must not contain path separators")
        if not self.unity_generated_root.startswith("Assets/") or ".." in self.unity_generated_root or "\\" in self.unity_generated_root:
            raise ValueError("unity_generated_root must be a forward-slash Assets path")
        if not self.tiles or not all(isinstance(tile, TileDefinition) for tile in self.tiles):
            raise ValueError("tiles must contain at least one TileDefinition")
        pages = self.resolved_atlas_pages
        page_ids = [page.atlas_id for page in pages]
        if len(page_ids) != len(set(page_ids)):
            raise ValueError("atlas page ids must be unique")
        if self.tileset_profile is TileSetProfile.ADAPTIVE_HD:
            if not 1 <= len(pages) <= 3:
                raise ValueError("adaptive_hd must contain one to three atlas pages")
            if any(page.columns != 4 or page.rows != 4 for page in pages):
                raise ValueError("adaptive_hd atlas pages must use a 4x4 grid")
        elif len(pages) != 1:
            raise ValueError("standard_16 must contain exactly one atlas page")
        if len(self.tiles) > self.max_tile_count:
            raise ValueError("tiles must not exceed max_tile_count")
        tile_ids = [tile.tile_id for tile in self.tiles]
        if len(tile_ids) != len(set(tile_ids)):
            raise ValueError("tile ids must be unique")
        known_page_ids = set(page_ids)
        atlas_cells = [(tile.atlas_id, tile.atlas_column, tile.atlas_row) for tile in self.tiles]
        if len(atlas_cells) != len(set(atlas_cells)):
            raise ValueError("tile atlas cells must be unique")
        for tile in self.tiles:
            if tile.atlas_id not in known_page_ids:
                raise ValueError(f"tile references unknown atlas page: {tile.tile_id}")
            page = next(item for item in pages if item.atlas_id == tile.atlas_id)
            if tile.atlas_column >= page.columns or tile.atlas_row >= page.rows:
                raise ValueError(f"tile is outside the atlas grid: {tile.tile_id}")
        if not self.layers or not all(isinstance(layer, TileLayer) for layer in self.layers):
            raise ValueError("layers must contain at least one TileLayer")
        layer_ids = [layer.layer_id for layer in self.layers]
        if len(layer_ids) != len(set(layer_ids)):
            raise ValueError("layer ids must be unique")
        expected_cells = self.map_width * self.map_height
        known_tiles = set(tile_ids)
        for layer in self.layers:
            if len(layer.cells) != expected_cells:
                raise ValueError(f"layer cells must contain exactly {expected_cells} entries: {layer.layer_id}")
            unknown = {item for item in layer.cells if item is not None and item not in known_tiles}
            if unknown:
                raise ValueError(f"layer references unknown tiles: {layer.layer_id}: {sorted(unknown)}")
        adjacency_keys = [(rule.tile_id, rule.direction) for rule in self.adjacency_rules]
        if len(adjacency_keys) != len(set(adjacency_keys)):
            raise ValueError("adjacency rules must be unique per tile and direction")
        for rule in self.adjacency_rules:
            if rule.tile_id not in known_tiles or any(item not in known_tiles for item in rule.allowed_neighbors):
                raise ValueError("adjacency rules must reference known tiles")
        object.__setattr__(self, "reference_paths", tuple(normalize_repo_relative_path(path, field_name="reference_paths") for path in self.reference_paths))

    @property
    def resolved_atlas_pages(self) -> tuple[AtlasPageDefinition, ...]:
        if self.atlas_pages:
            return self.atlas_pages
        return (AtlasPageDefinition("page-01", self.atlas_columns, self.atlas_rows, self.tile_width, self.tile_height, self.prompt),)

    @property
    def expected_atlas_sizes(self) -> dict[str, tuple[int, int]]:
        return {
            page.atlas_id: (
                self.atlas_margin * 2 + page.columns * page.tile_width + (page.columns - 1) * self.atlas_spacing,
                self.atlas_margin * 2 + page.rows * page.tile_height + (page.rows - 1) * self.atlas_spacing,
            )
            for page in self.resolved_atlas_pages
        }

    @property
    def expected_atlas_size(self) -> tuple[int, int]:
        if len(self.resolved_atlas_pages) != 1:
            raise ValueError("expected_atlas_size is only available for single-page requests")
        return next(iter(self.expected_atlas_sizes.values()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "asset_id": self.asset_id,
            "prompt": self.prompt,
            "output_dir": self.output_dir,
            "source_preference": self.source_preference.value,
            "tile_width": self.tile_width,
            "tile_height": self.tile_height,
            "atlas_columns": self.atlas_columns,
            "atlas_rows": self.atlas_rows,
            "atlas_margin": self.atlas_margin,
            "atlas_spacing": self.atlas_spacing,
            "map_width": self.map_width,
            "map_height": self.map_height,
            "pixels_per_unit": self.pixels_per_unit,
            "filter_mode": self.filter_mode.value,
            "engine_target": self.engine_target.value,
            "palette_name": self.palette_name,
            "unity_generated_root": self.unity_generated_root,
            "tiles": [tile.to_dict() for tile in self.tiles],
            "layers": [layer.to_dict() for layer in self.layers],
            "reference_paths": list(self.reference_paths),
            "tileset_profile": self.tileset_profile.value,
            "max_tile_count": self.max_tile_count,
            "atlas_pages": [page.to_dict() for page in self.atlas_pages],
            "adjacency_rules": [rule.to_dict() for rule in self.adjacency_rules],
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TileMapRequest":
        return cls(
            schema_version=int(value["schema_version"]),
            asset_id=str(value["asset_id"]),
            prompt=str(value["prompt"]),
            output_dir=str(value["output_dir"]),
            source_preference=SourcePreference(value["source_preference"]),
            tile_width=int(value["tile_width"]),
            tile_height=int(value["tile_height"]),
            atlas_columns=int(value["atlas_columns"]),
            atlas_rows=int(value["atlas_rows"]),
            atlas_margin=int(value.get("atlas_margin", 0)),
            atlas_spacing=int(value.get("atlas_spacing", 0)),
            map_width=int(value["map_width"]),
            map_height=int(value["map_height"]),
            pixels_per_unit=int(value.get("pixels_per_unit", value["tile_width"])),
            filter_mode=TileFilterMode(value.get("filter_mode", "point")),
            engine_target=TilemapEngineTarget(value.get("engine_target", "Unity_Tilemap")),
            palette_name=str(value["palette_name"]),
            unity_generated_root=str(value["unity_generated_root"]),
            tiles=tuple(TileDefinition.from_dict(item) for item in value["tiles"]),
            layers=tuple(TileLayer.from_dict(item) for item in value["layers"]),
            reference_paths=tuple(str(item) for item in value.get("reference_paths", [])),
            tileset_profile=TileSetProfile(value.get("tileset_profile", "standard_16")),
            max_tile_count=int(value.get("max_tile_count", 16)),
            atlas_pages=tuple(AtlasPageDefinition.from_dict(item) for item in value.get("atlas_pages", [])),
            adjacency_rules=tuple(TileAdjacencyRule.from_dict(item) for item in value.get("adjacency_rules", [])),
        )
