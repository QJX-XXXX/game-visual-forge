from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from game_visual_forge.contracts import AtlasPageDefinition, RawImageRecord, TileMapRequest, TileMapSourceSet, load_tilemap_source_set
from game_visual_forge.contracts.serialization import dump_json
from game_visual_forge.errors import ErrorCode, ForgeError
from game_visual_forge.processing.images import _load_pillow, verify_image_unchanged
from game_visual_forge.processing.tilemap_quality import analyze_tilemap_quality, render_seam_preview, render_usage_preview, seam_samples, _tile_images
from game_visual_forge.processing.tilemap_objects import emit_object_artifacts


@dataclass(frozen=True)
class TileMapProcessingResult:
    schema_version: int
    staging_dir: str
    tileset_paths: tuple[str, ...]
    slices_path: str
    placement_path: str
    unity_manifest_path: str
    preview_path: str
    quality_metrics_path: str
    seam_preview_path: str
    usage_preview_path: str
    processing_steps: tuple[str, ...]
    needs_attention: bool
    building_entrances_path: str = ""
    objects_path: str = ""
    collision_path: str = ""
    asset_set_path: str = ""
    gameplay_crop_path: str = ""
    collision_preview_path: str = ""

    @property
    def tileset_path(self) -> str:
        if len(self.tileset_paths) != 1:
            raise ValueError("tileset_path is only available for single-page results")
        return self.tileset_paths[0]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "staging_dir": self.staging_dir,
            "tileset_paths": list(self.tileset_paths),
            "tileset_path": self.tileset_path if len(self.tileset_paths) == 1 else None,
            "slices_path": self.slices_path,
            "placement_path": self.placement_path,
            "unity_manifest_path": self.unity_manifest_path,
            "preview_path": self.preview_path,
            "quality_metrics_path": self.quality_metrics_path,
            "seam_preview_path": self.seam_preview_path,
            "usage_preview_path": self.usage_preview_path,
            "processing_steps": list(self.processing_steps),
            "needs_attention": self.needs_attention,
            "building_entrances_path": self.building_entrances_path,
            "objects_path": self.objects_path,
            "collision_path": self.collision_path,
            "asset_set_path": self.asset_set_path,
            "gameplay_crop_path": self.gameplay_crop_path,
            "collision_preview_path": self.collision_preview_path,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TileMapProcessingResult":
        if value.get("schema_version") != 1:
            raise ValueError("TileMapProcessingResult schema_version must be 1")
        paths = value.get("tileset_paths")
        if paths is None:
            paths = [value["tileset_path"]]
        return cls(
            schema_version=1,
            staging_dir=str(value["staging_dir"]),
            tileset_paths=tuple(str(path) for path in paths),
            slices_path=str(value["slices_path"]),
            placement_path=str(value["placement_path"]),
            unity_manifest_path=str(value["unity_manifest_path"]),
            preview_path=str(value["preview_path"]),
            quality_metrics_path=str(value.get("quality_metrics_path", "")),
            seam_preview_path=str(value.get("seam_preview_path", "")),
            usage_preview_path=str(value.get("usage_preview_path", "")),
            processing_steps=tuple(str(item) for item in value["processing_steps"]),
            needs_attention=bool(value["needs_attention"]),
            building_entrances_path=str(value.get("building_entrances_path", "")),
            objects_path=str(value.get("objects_path", "")),
            collision_path=str(value.get("collision_path", "")),
            asset_set_path=str(value.get("asset_set_path", "")),
            gameplay_crop_path=str(value.get("gameplay_crop_path", "")),
            collision_preview_path=str(value.get("collision_preview_path", "")),
        )


def _atlas_box(page: AtlasPageDefinition, column: int, row: int, margin: int, spacing: int) -> tuple[int, int, int, int]:
    left = margin + column * (page.tile_width + spacing)
    top = margin + row * (page.tile_height + spacing)
    return left, top, left + page.tile_width, top + page.tile_height


def _compose_preview(atlases: dict[str, Any], request: TileMapRequest) -> Any:
    Image = _load_pillow()
    preview = Image.new("RGBA", (request.map_width * request.tile_width, request.map_height * request.tile_height), (0, 0, 0, 0))
    pages = {page.atlas_id: page for page in request.resolved_atlas_pages}
    tiles = {
        tile.tile_id: atlases[tile.atlas_id].crop(_atlas_box(pages[tile.atlas_id], tile.atlas_column, tile.atlas_row, request.atlas_margin, request.atlas_spacing))
        for tile in request.tiles
    }
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
    record: RawImageRecord | TileMapSourceSet,
    output_dir: Path,
) -> TileMapProcessingResult:
    source_set = load_tilemap_source_set(record.to_dict(), request)
    if not isinstance(source_set, TileMapSourceSet):
        raise TypeError("tilemap source must be RawImageRecord or TileMapSourceSet")
    for page in source_set.pages:
        verify_image_unchanged(repo_root, page.image)
    Image = _load_pillow()
    pages = {page.atlas_id: page for page in request.resolved_atlas_pages}
    atlases: dict[str, Any] = {}
    for source in source_set.pages:
        source_path = repo_root.resolve() / PurePosixPath(source.image.path)
        with Image.open(source_path) as opened:
            atlas = opened.convert("RGBA")
        expected_size = request.expected_atlas_sizes[source.atlas_id]
        if atlas.size != expected_size:
            raise ForgeError(
                ErrorCode.INVALID_REQUEST,
                "tileset dimensions must match the declared atlas grid",
                recoverable=True,
                context={"atlas_id": source.atlas_id, "source_size": atlas.size, "expected_size": expected_size},
            )
        atlases[source.atlas_id] = atlas

    fingerprint = source_set.pages[0].image.request_fingerprint
    source_hash = source_set.pages[0].image.sha256
    staging = output_dir.parent / f".{output_dir.name}.tile-staging-{source_hash[:12]}-{fingerprint[:8]}"
    staging.mkdir(parents=True, exist_ok=True)
    tileset_paths = []
    for index, source in enumerate(source_set.pages, start=1):
        filename = "tileset.png" if len(source_set.pages) == 1 else f"tileset-{source.atlas_id}.png"
        atlases[source.atlas_id].save(staging / filename, format="PNG")
        tileset_paths.append(filename)

    slices = []
    for tile in request.tiles:
        page = pages[tile.atlas_id]
        left, top, right, bottom = _atlas_box(page, tile.atlas_column, tile.atlas_row, request.atlas_margin, request.atlas_spacing)
        slices.append({
            "id": tile.tile_id,
            "name": tile.tile_id,
            "atlas_column": tile.atlas_column,
            "atlas_row": tile.atlas_row,
            "atlas_id": tile.atlas_id,
            "rect": {
                "x": left,
                "y": atlas.height - bottom,
                "width": right - left,
                "height": bottom - top,
            },
            "palette": {"x": list(pages).index(tile.atlas_id) * page.columns + tile.atlas_column, "y": page.rows - 1 - tile.atlas_row},
            "collider_type": tile.collider_type.value,
            "semantic_role": tile.semantic_role.value,
        })
    atlas_metadata = []
    for source in source_set.pages:
        page = pages[source.atlas_id]
        atlas_metadata.append({
            "atlas_id": source.atlas_id,
            "path": tileset_paths[len(atlas_metadata)],
            "width": atlases[source.atlas_id].width,
            "height": atlases[source.atlas_id].height,
            "columns": page.columns,
            "rows": page.rows,
            "tile_width": page.tile_width,
            "tile_height": page.tile_height,
            "margin": request.atlas_margin,
            "spacing": request.atlas_spacing,
        })
    dump_json(staging / "tileset-slices.json", {
        "schema_version": 1,
        "coordinate_origin": "bottom-left",
        "atlas": atlas_metadata[0] if len(atlas_metadata) == 1 else None,
        "atlases": atlas_metadata,
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
        "bridge_connectivity_rules": [rule.to_dict() for rule in request.bridge_connectivity_rules],
        "layers": placement_layers,
    })

    dump_json(staging / "building-entrances.json", {
        "schema_version": 1,
        "map_id": request.asset_id,
        "coordinate_system": "top-left-grid",
        "transition_implementation": "out-of-scope",
        "entries": [
            {
                "id": entrance.entrance_id,
                "layer_id": entrance.layer_id,
                "cell": {"x": entrance.x, "y": entrance.y},
                "target_scene_id": entrance.target_scene_id,
                "target_spawn_id": entrance.target_spawn_id,
            }
            for entrance in request.building_entrances
        ],
    })

    dump_json(staging / "unity-tilemap.json", {
        "schema_version": 1,
        "asset_id": request.asset_id,
        "engine_target": request.engine_target.value,
        "minimum_unity_version": "2022.3",
        "importer_version": "0.1.0",
        "tileset": tileset_paths[0] if len(tileset_paths) == 1 else None,
        "tilesets": [{"atlas_id": item["atlas_id"], "path": item["path"]} for item in atlas_metadata],
        "slices": "tileset-slices.json",
        "placement": "tilemap-placement.json",
        "building_entrances": "building-entrances.json",
        "palette_name": request.palette_name,
        "generated_root": request.unity_generated_root,
        "tile_size_mode": request.tile_size_mode.value,
        "tile_width": request.tile_width,
        "tile_height": request.tile_height,
        "pixels_per_unit": request.pixels_per_unit,
        "filter_mode": request.filter_mode.value,
        "prefab_name": f"{request.asset_id}-tilemap",
        "required_packages": ["com.unity.2d.sprite", "com.unity.2d.tilemap"],
        "bridge_connectivity_rules": [rule.to_dict() for rule in request.bridge_connectivity_rules],
        "objects": "tilemap-objects.json" if request.object_assets else None,
        "collision": "tilemap-collision.json" if request.object_assets else None,
        "asset_set": "asset-set.json" if request.object_assets else None,
        "gameplay_crop": "tilemap-gameplay-crop.png" if request.gameplay_crop is not None else None,
        "collision_preview": "tilemap-collision-preview.png" if request.object_assets else None,
    })
    preview = _compose_preview(atlases, request)
    preview.save(staging / "tilemap-preview.png", format="PNG")
    metrics = analyze_tilemap_quality(atlases, request)
    dump_json(staging / "tilemap-quality-metrics.json", metrics.to_dict())
    render_seam_preview(preview, seam_samples(atlases, request), request).save(staging / "tile-seam-preview.png", format="PNG")
    render_usage_preview(_tile_images(atlases, request), metrics.usage_counts, request).save(staging / "tile-usage-preview.png", format="PNG")

    object_paths = {}
    if request.object_assets:
        object_paths = emit_object_artifacts(staging, repo_root, request, source_set, preview)

    return TileMapProcessingResult(
        schema_version=1,
        staging_dir=PurePosixPath(staging.resolve().relative_to(repo_root.resolve()).as_posix()).as_posix(),
        tileset_paths=tuple(tileset_paths),
        slices_path="tileset-slices.json",
        placement_path="tilemap-placement.json",
        unity_manifest_path="unity-tilemap.json",
        preview_path="tilemap-preview.png",
        quality_metrics_path="tilemap-quality-metrics.json",
        seam_preview_path="tile-seam-preview.png",
        usage_preview_path="tile-usage-preview.png",
        processing_steps=(
            "verify-tileset-source",
            "validate-atlas-grid",
            "emit-unity-sprite-slices",
            "emit-tilemap-placement",
            "emit-building-entrances",
            "emit-unity-import-manifest",
            "compose-tilemap-preview",
            "validate-bridge-connectivity",
        ),
        needs_attention=metrics.needs_attention,
        building_entrances_path="building-entrances.json",
        **object_paths,
    )
