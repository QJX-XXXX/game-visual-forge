from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from game_visual_forge.contracts import TileMapRequest, TileSemanticRole

SEAM_ATTENTION_THRESHOLD = 48.0
DECORATION_USAGE_RATIO_THRESHOLD = 0.25


@dataclass(frozen=True)
class InvalidAdjacency:
    layer_id: str
    x: int
    y: int
    tile_id: str
    direction: str
    neighbor_id: str

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "InvalidAdjacency":
        return cls(str(value["layer_id"]), int(value["x"]), int(value["y"]), str(value["tile_id"]), str(value["direction"]), str(value["neighbor_id"]))


@dataclass(frozen=True)
class TileMapQualityMetrics:
    max_seam_score: float
    seam_pair_count: int
    clipped_tile_ids: tuple[str, ...]
    usage_counts: dict[str, int]
    unused_tile_ids: tuple[str, ...]
    overused_decoration_ids: tuple[str, ...]
    invalid_adjacencies: tuple[InvalidAdjacency, ...]
    needs_attention: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "max_seam_score": self.max_seam_score,
            "seam_pair_count": self.seam_pair_count,
            "clipped_tile_ids": list(self.clipped_tile_ids),
            "usage_counts": dict(sorted(self.usage_counts.items())),
            "unused_tile_ids": list(self.unused_tile_ids),
            "overused_decoration_ids": list(self.overused_decoration_ids),
            "invalid_adjacencies": [item.to_dict() for item in self.invalid_adjacencies],
            "needs_attention": self.needs_attention,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TileMapQualityMetrics":
        if value.get("schema_version") != 1:
            raise ValueError("TileMapQualityMetrics schema_version must be 1")
        return cls(
            float(value["max_seam_score"]), int(value["seam_pair_count"]),
            tuple(str(item) for item in value["clipped_tile_ids"]),
            {str(key): int(item) for key, item in value["usage_counts"].items()},
            tuple(str(item) for item in value["unused_tile_ids"]),
            tuple(str(item) for item in value["overused_decoration_ids"]),
            tuple(InvalidAdjacency.from_dict(item) for item in value["invalid_adjacencies"]),
            bool(value["needs_attention"]),
        )


def _tile_images(atlases: dict[str, Any], request: TileMapRequest) -> dict[str, Any]:
    pages = {page.atlas_id: page for page in request.resolved_atlas_pages}
    result = {}
    for tile in request.tiles:
        page = pages[tile.atlas_id]
        left = request.atlas_margin + tile.atlas_column * (page.tile_width + request.atlas_spacing)
        top = request.atlas_margin + tile.atlas_row * (page.tile_height + request.atlas_spacing)
        result[tile.tile_id] = atlases[tile.atlas_id].crop((left, top, left + page.tile_width, top + page.tile_height))
    return result


def _edge_score(left: Any, right: Any, vertical: bool) -> float:
    pixels = []
    if vertical:
        x1, x2 = left.width - 1, 0
        for y in range(min(left.height, right.height)):
            pixels.append((left.getpixel((x1, y)), right.getpixel((x2, y))))
    else:
        y1, y2 = left.height - 1, 0
        for x in range(min(left.width, right.width)):
            pixels.append((left.getpixel((x, y1)), right.getpixel((x, y2))))
    if not pixels:
        return 0.0
    return sum(sum(abs(a - b) for a, b in zip(first[:4], second[:4])) / 4 for first, second in pixels) / len(pixels)


def seam_samples(atlases: dict[str, Any], request: TileMapRequest) -> tuple[tuple[int, int, int, int, float], ...]:
    tiles = _tile_images(atlases, request)
    samples = []
    for layer in request.layers:
        for index, tile_id in enumerate(layer.cells):
            if tile_id is None:
                continue
            x, y = index % request.map_width, index // request.map_width
            if x + 1 < request.map_width and layer.cells[index + 1] is not None:
                score = _edge_score(tiles[tile_id], tiles[layer.cells[index + 1]], True)
                samples.append((x + 1, y, x + 1, y + 1, score))
            if y + 1 < request.map_height and layer.cells[index + request.map_width] is not None:
                score = _edge_score(tiles[tile_id], tiles[layer.cells[index + request.map_width]], False)
                samples.append((x, y + 1, x + 1, y + 1, score))
    return tuple(samples)


def analyze_tilemap_quality(atlases: dict[str, Any], request: TileMapRequest) -> TileMapQualityMetrics:
    tiles = _tile_images(atlases, request)
    definitions = {tile.tile_id: tile for tile in request.tiles}
    usage = {tile.tile_id: 0 for tile in request.tiles}
    clipped = set()
    overused = set()
    invalid = []
    samples = seam_samples(atlases, request)
    for layer in request.layers:
        non_empty = 0
        for index, tile_id in enumerate(layer.cells):
            if tile_id is None:
                continue
            usage[tile_id] += 1
            non_empty += 1
            tile = definitions[tile_id]
            if tile.semantic_role in {TileSemanticRole.DECORATION, TileSemanticRole.PROP}:
                image = tiles[tile_id]
                alpha = image.getchannel("A")
                if alpha.getextrema()[0] == 0:
                    edge_pixels = [alpha.getpixel((x, 0)) for x in range(image.width)] + [alpha.getpixel((x, image.height - 1)) for x in range(image.width)] + [alpha.getpixel((0, y)) for y in range(image.height)] + [alpha.getpixel((image.width - 1, y)) for y in range(image.height)]
                    if any(value > 0 for value in edge_pixels):
                        clipped.add(tile_id)
            x, y = index % request.map_width, index // request.map_width
            for direction, dx, dy in (("north", 0, 1), ("east", 1, 0), ("south", 0, -1), ("west", -1, 0)):
                rule = next((item for item in request.adjacency_rules if item.tile_id == tile_id and item.direction.value == direction), None)
                nx, ny = x + dx, y + dy
                if rule is not None and 0 <= nx < request.map_width and 0 <= ny < request.map_height:
                    neighbor = layer.cells[ny * request.map_width + nx]
                    if neighbor is not None and neighbor not in rule.allowed_neighbors:
                        invalid.append(InvalidAdjacency(layer.layer_id, x, y, tile_id, direction, neighbor))
        if non_empty:
            for tile_id, count in usage.items():
                if definitions[tile_id].semantic_role in {TileSemanticRole.DECORATION, TileSemanticRole.PROP} and count / non_empty > DECORATION_USAGE_RATIO_THRESHOLD:
                    overused.add(tile_id)
    max_score = max((sample[-1] for sample in samples), default=0.0)
    return TileMapQualityMetrics(max_score, len(samples), tuple(sorted(clipped)), usage, tuple(sorted(tile_id for tile_id, count in usage.items() if count == 0)), tuple(sorted(overused)), tuple(invalid), max_score > SEAM_ATTENTION_THRESHOLD or bool(clipped) or bool(overused) or bool(invalid))


def render_seam_preview(preview: Any, samples: tuple[tuple[int, int, int, int, float], ...], request: TileMapRequest) -> Any:
    from PIL import ImageDraw
    result = preview.copy()
    draw = ImageDraw.Draw(result)
    for x1, y1, x2, y2, score in samples:
        if score > SEAM_ATTENTION_THRESHOLD:
            color = (255, 40, 40, 230)
        elif score > SEAM_ATTENTION_THRESHOLD * 0.65:
            color = (255, 180, 40, 220)
        else:
            color = (40, 220, 120, 180)
        draw.line(
            (x1 * request.tile_width, y1 * request.tile_height, x2 * request.tile_width, y2 * request.tile_height),
            fill=color,
            width=max(2, min(request.tile_width, request.tile_height) // 64),
        )
    return result


def render_usage_preview(tiles: dict[str, Any], usage_counts: dict[str, int], request: TileMapRequest) -> Any:
    from PIL import Image, ImageDraw
    columns = 4
    tile_width, tile_height = request.tile_width, request.tile_height
    cell_width, cell_height = tile_width + 8, tile_height + 12
    rows = (len(request.tiles) + columns - 1) // columns
    canvas = Image.new("RGBA", (columns * cell_width, rows * cell_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    max_count = max(usage_counts.values(), default=0)
    for index, tile in enumerate(request.tiles):
        x, y = (index % columns) * cell_width, (index // columns) * cell_height
        canvas.alpha_composite(tiles[tile.tile_id], (x, y))
        width = 0 if max_count == 0 else round(tile_width * usage_counts[tile.tile_id] / max_count)
        draw.rectangle((x, y + tile_height + 2, x + width, y + tile_height + 5), fill=(40, 220, 120, 255))
    return canvas
