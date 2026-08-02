from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from game_visual_forge.contracts import RawImageRecord, TileMapRequest
from game_visual_forge.contracts.serialization import dump_json
from game_visual_forge.errors import ErrorCode, ForgeError
from game_visual_forge.processing.images import _load_pillow, verify_image_unchanged


@dataclass(frozen=True)
class TileMapProcessingResult:
    schema_version: int
    staging_dir: str
    tileset_path: str
    slices_path: str
    placement_path: str
    unity_manifest_path: str
    preview_path: str
    processing_steps: tuple[str, ...]
    needs_attention: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "staging_dir": self.staging_dir,
            "tileset_path": self.tileset_path,
            "slices_path": self.slices_path,
            "placement_path": self.placement_path,
            "unity_manifest_path": self.unity_manifest_path,
            "preview_path": self.preview_path,
            "processing_steps": list(self.processing_steps),
            "needs_attention": self.needs_attention,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TileMapProcessingResult":
        if value.get("schema_version") != 1:
            raise ValueError("TileMapProcessingResult schema_version must be 1")
        return cls(
            schema_version=1,
            staging_dir=str(value["staging_dir"]),
            tileset_path=str(value["tileset_path"]),
            slices_path=str(value["slices_path"]),
            placement_path=str(value["placement_path"]),
            unity_manifest_path=str(value["unity_manifest_path"]),
            preview_path=str(value["preview_path"]),
            processing_steps=tuple(str(item) for item in value["processing_steps"]),
            needs_attention=bool(value["needs_attention"]),
        )


def _atlas_box(request: TileMapRequest, column: int, row: int) -> tuple[int, int, int, int]:
    left = request.atlas_margin + column * (request.tile_width + request.atlas_spacing)
    top = request.atlas_margin + row * (request.tile_height + request.atlas_spacing)
    return left, top, left + request.tile_width, top + request.tile_height


def _compose_preview(atlas: Any, request: TileMapRequest) -> Any:
    Image = _load_pillow()
    preview = Image.new("RGBA", (request.map_width * request.tile_width, request.map_height * request.tile_height), (0, 0, 0, 0))
    tiles = {tile.tile_id: atlas.crop(_atlas_box(request, tile.atlas_column, tile.atlas_row)) for tile in request.tiles}
    for layer in sorted(request.layers, key=lambda item: item.sorting_order):
        for index, tile_id in enumerate(layer.cells):
            if tile_id is None:
                continue
            column = index % request.map_width
            row = index // request.map_width
            preview.alpha_composite(tiles[tile_id], (column * request.tile_width, row * request.tile_height))
    return preview


def process_tilemap(
    repo_root: Path,
    request: TileMapRequest,
    record: RawImageRecord,
    output_dir: Path,
) -> TileMapProcessingResult:
    verify_image_unchanged(repo_root, record)
    Image = _load_pillow()
    source_path = repo_root.resolve() / PurePosixPath(record.path)
    with Image.open(source_path) as opened:
        atlas = opened.convert("RGBA")
    if atlas.size != request.expected_atlas_size:
        raise ForgeError(
            ErrorCode.INVALID_REQUEST,
            "tileset dimensions must match the declared atlas grid",
            recoverable=True,
            context={"source_size": atlas.size, "expected_size": request.expected_atlas_size},
        )

    staging = output_dir.parent / f".{output_dir.name}.tile-staging-{record.sha256[:12]}-{record.request_fingerprint[:8]}"
    staging.mkdir(parents=True, exist_ok=True)
    atlas.save(staging / "tileset.png", format="PNG")

    slices = []
    for tile in request.tiles:
        left, top, right, bottom = _atlas_box(request, tile.atlas_column, tile.atlas_row)
        slices.append({
            "id": tile.tile_id,
            "name": tile.tile_id,
            "atlas_column": tile.atlas_column,
            "atlas_row": tile.atlas_row,
            "rect": {
                "x": left,
                "y": atlas.height - bottom,
                "width": right - left,
                "height": bottom - top,
            },
            "palette": {"x": tile.atlas_column, "y": request.atlas_rows - 1 - tile.atlas_row},
            "collider_type": tile.collider_type.value,
        })
    dump_json(staging / "tileset-slices.json", {
        "schema_version": 1,
        "coordinate_origin": "bottom-left",
        "atlas": {
            "width": atlas.width,
            "height": atlas.height,
            "columns": request.atlas_columns,
            "rows": request.atlas_rows,
            "tile_width": request.tile_width,
            "tile_height": request.tile_height,
            "margin": request.atlas_margin,
            "spacing": request.atlas_spacing,
        },
        "tiles": slices,
    })

    placement_layers = []
    for layer in request.layers:
        placements = []
        for index, tile_id in enumerate(layer.cells):
            if tile_id is None:
                continue
            column = index % request.map_width
            top_row = index // request.map_width
            placements.append({"x": column, "y": request.map_height - 1 - top_row, "tile_id": tile_id})
        placement_layers.append({
            "id": layer.layer_id,
            "sorting_order": layer.sorting_order,
            "has_collider": layer.has_collider,
            "placements": placements,
        })
    dump_json(staging / "tilemap-placement.json", {
        "schema_version": 1,
        "coordinate_origin": "bottom-left",
        "map_size": {"width": request.map_width, "height": request.map_height},
        "layers": placement_layers,
    })

    dump_json(staging / "unity-tilemap.json", {
        "schema_version": 1,
        "asset_id": request.asset_id,
        "engine_target": request.engine_target.value,
        "minimum_unity_version": "2022.3",
        "importer_version": "0.1.0",
        "tileset": "tileset.png",
        "slices": "tileset-slices.json",
        "placement": "tilemap-placement.json",
        "palette_name": request.palette_name,
        "generated_root": request.unity_generated_root,
        "pixels_per_unit": request.pixels_per_unit,
        "filter_mode": request.filter_mode.value,
        "prefab_name": f"{request.asset_id}-tilemap",
        "required_packages": ["com.unity.2d.sprite", "com.unity.2d.tilemap"],
    })
    _compose_preview(atlas, request).save(staging / "tilemap-preview.png", format="PNG")

    return TileMapProcessingResult(
        schema_version=1,
        staging_dir=PurePosixPath(staging.resolve().relative_to(repo_root.resolve()).as_posix()).as_posix(),
        tileset_path="tileset.png",
        slices_path="tileset-slices.json",
        placement_path="tilemap-placement.json",
        unity_manifest_path="unity-tilemap.json",
        preview_path="tilemap-preview.png",
        processing_steps=(
            "verify-tileset-source",
            "validate-atlas-grid",
            "emit-unity-sprite-slices",
            "emit-tilemap-placement",
            "emit-unity-import-manifest",
            "compose-tilemap-preview",
        ),
        needs_attention=False,
    )
