from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from game_visual_forge.contracts import MapRequest, MapShape, MapShapeType, RawImageRecord
from game_visual_forge.contracts.serialization import dump_json
from game_visual_forge.errors import ErrorCode, ForgeError
from game_visual_forge.processing.images import _load_pillow, verify_image_unchanged


@dataclass(frozen=True)
class MapProcessingResult:
    schema_version: int
    staging_dir: str
    base_map_path: str
    runtime_path: str
    walkable_mask_path: str
    collision_mask_path: str
    preview_path: str
    processing_steps: tuple[str, ...]
    needs_attention: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "staging_dir": self.staging_dir,
            "base_map_path": self.base_map_path,
            "runtime_path": self.runtime_path,
            "walkable_mask_path": self.walkable_mask_path,
            "collision_mask_path": self.collision_mask_path,
            "preview_path": self.preview_path,
            "processing_steps": list(self.processing_steps),
            "needs_attention": self.needs_attention,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "MapProcessingResult":
        if value.get("schema_version") != 1:
            raise ValueError("MapProcessingResult schema_version must be 1")
        return cls(
            schema_version=1,
            staging_dir=str(value["staging_dir"]),
            base_map_path=str(value["base_map_path"]),
            runtime_path=str(value["runtime_path"]),
            walkable_mask_path=str(value["walkable_mask_path"]),
            collision_mask_path=str(value["collision_mask_path"]),
            preview_path=str(value["preview_path"]),
            processing_steps=tuple(str(item) for item in value["processing_steps"]),
            needs_attention=bool(value["needs_attention"]),
        )


def _draw_shape(draw: Any, shape: MapShape, *, fill: int, outline: int | None = None) -> None:
    if shape.shape_type is MapShapeType.RECT:
        assert shape.width is not None and shape.height is not None
        box = (shape.x, shape.y, shape.x + shape.width - 1, shape.y + shape.height - 1)
        draw.rectangle(box, fill=fill, outline=outline)
    elif shape.shape_type is MapShapeType.CIRCLE:
        assert shape.radius is not None
        box = (shape.x - shape.radius, shape.y - shape.radius, shape.x + shape.radius, shape.y + shape.radius)
        draw.ellipse(box, fill=fill, outline=outline)
    elif shape.shape_type is MapShapeType.ELLIPSE:
        assert shape.radius_x is not None and shape.radius_y is not None
        box = (shape.x - shape.radius_x, shape.y - shape.radius_y, shape.x + shape.radius_x, shape.y + shape.radius_y)
        draw.ellipse(box, fill=fill, outline=outline)
    else:
        points = [(point.x, point.y) for point in shape.points]
        draw.polygon(points, fill=fill)
        if outline is not None:
            draw.line(points + [points[0]], fill=outline, width=2)


def _mask_for_shapes(image_size: tuple[int, int], shapes: tuple[MapShape, ...]) -> Any:
    Image = _load_pillow()
    from PIL import ImageDraw
    mask = Image.new("L", image_size, 0)
    draw = ImageDraw.Draw(mask)
    for shape in shapes:
        _draw_shape(draw, shape, fill=255)
    return mask


def _debug_preview(source: Any, request: MapRequest, walkable: Any, collision: Any) -> Any:
    Image = _load_pillow()
    from PIL import ImageDraw
    preview = source.convert("RGBA")
    collision_overlay = Image.new("RGBA", preview.size, (220, 50, 50, 86))
    collision_overlay.putalpha(Image.eval(collision, lambda value: min(86, value * 86 // 255)))
    preview.alpha_composite(collision_overlay)
    walkable_overlay = Image.new("RGBA", preview.size, (40, 190, 90, 92))
    walkable_overlay.putalpha(Image.eval(walkable, lambda value: min(92, value * 92 // 255)))
    preview.alpha_composite(walkable_overlay)
    draw = ImageDraw.Draw(preview)
    for shape in (*request.walk_bounds, *request.blockers, *request.zones):
        color = (40, 220, 100, 255) if shape in request.walk_bounds else (230, 70, 70, 255) if shape in request.blockers else (70, 120, 255, 255)
        _draw_shape(draw, shape, fill=None, outline=color)
    draw.ellipse((request.spawn.x - 5, request.spawn.y - 5, request.spawn.x + 5, request.spawn.y + 5), fill=(255, 220, 40, 255))
    return preview


def process_map(repo_root: Path, request: MapRequest, record: RawImageRecord, output_dir: Path) -> MapProcessingResult:
    verify_image_unchanged(repo_root, record)
    Image = _load_pillow()
    source_path = repo_root.resolve() / PurePosixPath(record.path)
    with Image.open(source_path) as opened:
        source = opened.convert("RGBA")
    if source.size != (request.canvas_width, request.canvas_height):
        raise ForgeError(
            ErrorCode.INVALID_REQUEST,
            "source image dimensions must match map canvas",
            recoverable=True,
            context={"source_size": source.size, "map_size": (request.canvas_width, request.canvas_height)},
        )
    walk_bounds = _mask_for_shapes(source.size, request.walk_bounds)
    blockers = _mask_for_shapes(source.size, request.blockers)
    from PIL import ImageChops
    walkable = ImageChops.subtract(walk_bounds, blockers)
    collision = ImageChops.invert(walkable)
    staging = output_dir.parent / f".{output_dir.name}.staging-{record.sha256[:12]}"
    staging.mkdir(parents=True, exist_ok=True)
    source.save(staging / "base-map.png", format="PNG")
    walkable.save(staging / "walkable-mask.png", format="PNG")
    collision.save(staging / "collision-mask.png", format="PNG")
    runtime = {
        "schema_version": 1,
        "asset_id": request.asset_id,
        "map_size": {"width": request.canvas_width, "height": request.canvas_height},
        "map_mode": request.map_mode,
        "perspective": request.perspective,
        "spawn": request.spawn.to_dict(),
        "walk_bounds": [shape.to_dict() for shape in request.walk_bounds],
        "blockers": [shape.to_dict() for shape in request.blockers],
        "zones": [shape.to_dict() for shape in request.zones],
        "artifacts": {
            "base_map": "base-map.png",
            "walkable_mask": "walkable-mask.png",
            "collision_mask": "collision-mask.png",
            "preview": "debug-preview.png",
        },
    }
    dump_json(staging / "map-runtime.json", runtime)
    _debug_preview(source, request, walkable, collision).save(staging / "debug-preview.png", format="PNG")
    return MapProcessingResult(
        schema_version=1,
        staging_dir=PurePosixPath(staging.resolve().relative_to(repo_root.resolve()).as_posix()).as_posix(),
        base_map_path="base-map.png",
        runtime_path="map-runtime.json",
        walkable_mask_path="walkable-mask.png",
        collision_mask_path="collision-mask.png",
        preview_path="debug-preview.png",
        processing_steps=("verify-source", "copy-base-map", "rasterize-walk-bounds", "subtract-blockers", "derive-collision-mask", "compose-debug-preview"),
        needs_attention=False,
    )
