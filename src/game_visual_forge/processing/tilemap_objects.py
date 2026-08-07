from __future__ import annotations

from pathlib import Path
from typing import Any

from game_visual_forge.contracts import TileMapRequest, TileObjectAssetDefinition
from game_visual_forge.errors import ErrorCode, ForgeError
from game_visual_forge.processing.images import _load_pillow, sha256_file


def validate_object_image(image: Any, definition: TileObjectAssetDefinition) -> None:
    if image.size != (definition.pixel_width, definition.pixel_height):
        raise ForgeError(ErrorCode.INVALID_REQUEST, "object image dimensions do not match definition", recoverable=True, context={"asset_id": definition.asset_id, "size": image.size, "expected": (definition.pixel_width, definition.pixel_height)})
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    if image.getchannel("A").getextrema() == (255, 255):
        raise ForgeError(ErrorCode.INVALID_REQUEST, "object image must contain transparency", recoverable=True, context={"asset_id": definition.asset_id})


def compose_object_layer(preview: Any, object_images: dict[str, Any], request: TileMapRequest) -> Any:
    composed = preview.copy()
    for placement in sorted(request.object_placements, key=lambda item: item.sorting_order):
        image = object_images[placement.asset_id]
        composed.alpha_composite(image, (placement.x * request.tile_width, placement.y * request.tile_height))
    return composed


def build_object_manifest(request: TileMapRequest, copied_paths: dict[str, str]) -> dict[str, Any]:
    definitions = []
    for asset in request.object_assets:
        definitions.append({**asset.to_dict(), "path": copied_paths[asset.asset_id]})
    return {
        "schema_version": 1,
        "map_id": request.asset_id,
        "coordinate_system": "top-left-grid",
        "assets": definitions,
        "placements": [item.to_dict() for item in request.object_placements],
        "entrances": [item.to_dict() for item in request.object_entrances],
    }


def build_collision_manifest(request: TileMapRequest) -> dict[str, Any]:
    assets = {item.asset_id: item for item in request.object_assets}
    tile_definitions = {item.tile_id: item for item in request.tiles}
    blockers: list[dict[str, int | str]] = []
    for placement in request.object_placements:
        definition = assets[placement.asset_id]
        for cell in definition.collision_cells:
            blockers.append({"instance_id": placement.instance_id, "x": placement.x + cell.x, "y": placement.y + cell.y})
    entrances = []
    for entrance in request.object_entrances:
        placement = next(item for item in request.object_placements if item.instance_id == entrance.instance_id)
        definition = assets[placement.asset_id]
        if definition.doorway_cell is None:
            continue
        entrances.append({**entrance.to_dict(), "cell": {"x": placement.x + definition.doorway_cell.x, "y": placement.y + definition.doorway_cell.y}})
    terrain_blockers = []
    for layer in request.layers:
        for index, tile_id in enumerate(layer.cells):
            if tile_id is None or tile_definitions[tile_id].collider_type.value == "none":
                continue
            terrain_blockers.append({
                "layer_id": layer.layer_id,
                "tile_id": tile_id,
                "x": index % request.map_width,
                "y": index // request.map_width,
            })
    return {
        "schema_version": 1,
        "map_id": request.asset_id,
        "coordinate_system": "top-left-grid",
        "blocked_cells": blockers,
        "terrain_blocked_cells": terrain_blockers,
        "entrances": entrances,
        "road_connectivity_policy": request.road_connectivity_policy.value,
        "road_connection_requirements": [item.to_dict() for item in request.road_connection_requirements],
        "bridge_connectivity_rules": [item.to_dict() for item in request.bridge_connectivity_rules],
    }


def emit_object_artifacts(staging: Path, repo_root: Path, request: TileMapRequest, source_set: Any, preview: Any) -> dict[str, str]:
    Image = _load_pillow()
    object_dir = staging / "objects"
    object_dir.mkdir(parents=True, exist_ok=True)
    definitions = {item.asset_id: item for item in request.object_assets}
    object_images: dict[str, Any] = {}
    copied_paths: dict[str, str] = {}
    hashes: list[dict[str, str]] = []
    for source in source_set.objects:
        definition = definitions[source.asset_id]
        source_path = repo_root.resolve() / Path(source.image.path)
        with Image.open(source_path) as opened:
            image = opened.convert("RGBA")
        validate_object_image(image, definition)
        target = object_dir / f"{source.asset_id}.png"
        image.save(target, format="PNG")
        object_images[source.asset_id] = image
        copied_paths[source.asset_id] = f"objects/{source.asset_id}.png"
        hashes.append({"path": copied_paths[source.asset_id], "sha256": sha256_file(target)})
    dump = {
        "objects": build_object_manifest(request, copied_paths),
        "collision": build_collision_manifest(request),
    }
    from game_visual_forge.contracts.serialization import dump_json
    dump_json(staging / "tilemap-objects.json", dump["objects"])
    dump_json(staging / "tilemap-collision.json", dump["collision"])
    composed = compose_object_layer(preview, object_images, request)
    composed.save(staging / "tilemap-preview.png", format="PNG")
    if request.gameplay_crop is not None:
        crop = request.gameplay_crop
        composed.crop((crop.x * request.tile_width, crop.y * request.tile_height, (crop.x + crop.width) * request.tile_width, (crop.y + crop.height) * request.tile_height)).save(staging / "tilemap-gameplay-crop.png", format="PNG")
    overlay = composed.copy()
    from PIL import ImageDraw
    draw = ImageDraw.Draw(overlay, "RGBA")
    for blocker in dump["collision"]["blocked_cells"]:
        x, y = blocker["x"] * request.tile_width, blocker["y"] * request.tile_height
        draw.rectangle((x, y, x + request.tile_width - 1, y + request.tile_height - 1), fill=(220, 40, 40, 100), outline=(220, 40, 40, 220))
    for blocker in dump["collision"]["terrain_blocked_cells"]:
        x, y = blocker["x"] * request.tile_width, blocker["y"] * request.tile_height
        draw.rectangle((x, y, x + request.tile_width - 1, y + request.tile_height - 1), fill=(40, 90, 220, 90), outline=(40, 90, 220, 210))
    overlay.save(staging / "tilemap-collision-preview.png", format="PNG")
    terrain_hashes = []
    for source in source_set.pages:
        terrain_hashes.append({"path": f"tileset-{source.atlas_id}.png" if len(source_set.pages) > 1 else "tileset.png", "sha256": sha256_file(staging / (f"tileset-{source.atlas_id}.png" if len(source_set.pages) > 1 else "tileset.png"))})
    dump_json(staging / "asset-set.json", {"schema_version": 1, "terrain": terrain_hashes, "objects": hashes})
    return {
        "objects_path": "tilemap-objects.json", "collision_path": "tilemap-collision.json", "asset_set_path": "asset-set.json",
        "gameplay_crop_path": "tilemap-gameplay-crop.png" if request.gameplay_crop is not None else "",
        "collision_preview_path": "tilemap-collision-preview.png",
    }
