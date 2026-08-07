from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from game_visual_forge.contracts import TileMapRequest, TileObjectKind, TileSemanticRole


@dataclass(frozen=True)
class ObjectQualityMetrics:
    alpha_failures: tuple[str, ...] = ()
    silhouette_failures: tuple[str, ...] = ()
    overlap_failures: tuple[str, ...] = ()
    density_failures: tuple[str, ...] = ()
    entrance_failures: tuple[str, ...] = ()
    road_connectivity_failures: tuple[str, ...] = ()
    water_collision_failures: tuple[str, ...] = ()
    bridge_traversal_failures: tuple[str, ...] = ()

    @property
    def needs_attention(self) -> bool:
        return any((self.alpha_failures, self.silhouette_failures, self.overlap_failures, self.density_failures, self.entrance_failures, self.road_connectivity_failures, self.water_collision_failures, self.bridge_traversal_failures))

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": 1, "needs_attention": self.needs_attention, "alpha_failures": list(self.alpha_failures), "silhouette_failures": list(self.silhouette_failures), "overlap_failures": list(self.overlap_failures), "density_failures": list(self.density_failures), "entrance_failures": list(self.entrance_failures), "road_connectivity_failures": list(self.road_connectivity_failures), "water_collision_failures": list(self.water_collision_failures), "bridge_traversal_failures": list(self.bridge_traversal_failures)}


def _components(image: Any) -> tuple[int, int]:
    alpha = image.getchannel("A")
    pixels = alpha.load()
    occupied = {(x, y) for y in range(alpha.height) for x in range(alpha.width) if pixels[x, y] > 0}
    total = len(occupied)
    largest = 0
    while occupied:
        start = occupied.pop()
        stack = [start]
        size = 1
        while stack:
            x, y = stack.pop()
            for neighbor in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if neighbor in occupied:
                    occupied.remove(neighbor)
                    stack.append(neighbor)
                    size += 1
        largest = max(largest, size)
    return largest, total


def analyze_object_quality(request: TileMapRequest, object_images: dict[str, Any]) -> ObjectQualityMetrics:
    definitions = {item.asset_id: item for item in request.object_assets}
    alpha: list[str] = []
    silhouette: list[str] = []
    hashes: dict[str, str] = {}
    for asset_id, definition in definitions.items():
        image = object_images.get(asset_id)
        if image is None:
            alpha.append(asset_id)
            continue
        if image.size != (definition.pixel_width, definition.pixel_height) or image.getchannel("A").getextrema() == (255, 255):
            alpha.append(asset_id)
        largest, total = _components(image)
        if total and largest / total < 0.90:
            silhouette.append(asset_id)
        if definition.kind is TileObjectKind.BUILDING:
            hashes[asset_id] = hashlib.sha256(image.tobytes()).hexdigest()
    duplicate_ids = [asset_id for asset_id, digest in hashes.items() if list(hashes.values()).count(digest) > 1]
    silhouette.extend(f"duplicate:{asset_id}" for asset_id in sorted(set(duplicate_ids)))

    overlap: list[str] = []
    occupied: dict[tuple[int, int], str] = {}
    density: list[str] = []
    assets = definitions
    for placement in request.object_placements:
        definition = assets[placement.asset_id]
        instances = [item for item in request.object_placements if item.asset_id == placement.asset_id]
        if len(instances) > definition.max_instances:
            density.append(placement.asset_id)
        for cell in definition.collision_cells:
            key = (placement.x + cell.x, placement.y + cell.y)
            if key in occupied:
                overlap.append(f"{occupied[key]}:{placement.instance_id}")
            occupied[key] = placement.instance_id
    entrance_failures = []
    blocked = set(occupied)
    for entrance in request.object_entrances:
        placement = next(item for item in request.object_placements if item.instance_id == entrance.instance_id)
        doorway = assets[placement.asset_id].doorway_cell
        if doorway is None or (placement.x + doorway.x, placement.y + doorway.y) in blocked:
            entrance_failures.append(entrance.entrance_id)

    road_failures: list[str] = []
    if request.road_connectivity_policy.value != "none":
        roads = set()
        for layer in request.layers:
            if request.road_layer_ids and layer.layer_id not in request.road_layer_ids:
                continue
            for index, tile_id in enumerate(layer.cells):
                if tile_id is not None and next(tile for tile in request.tiles if tile.tile_id == tile_id).semantic_role is TileSemanticRole.ROAD:
                    roads.add((index % request.map_width, index // request.map_width))
        for requirement in request.road_connection_requirements:
            if requirement.start not in roads or requirement.end not in roads:
                road_failures.append(requirement.rule_id)

    water_failures: list[str] = []
    tile_defs = {tile.tile_id: tile for tile in request.tiles}
    for layer in request.layers:
        for tile_id in layer.cells:
            if tile_id is not None and tile_defs[tile_id].semantic_role is TileSemanticRole.WATER and tile_defs[tile_id].collider_type.value == "none":
                water_failures.append(tile_id)

    return ObjectQualityMetrics(tuple(sorted(set(alpha))), tuple(sorted(set(silhouette))), tuple(sorted(set(overlap))), tuple(sorted(set(density))), tuple(sorted(set(entrance_failures))), tuple(sorted(set(road_failures))), tuple(sorted(set(water_failures))), ())
