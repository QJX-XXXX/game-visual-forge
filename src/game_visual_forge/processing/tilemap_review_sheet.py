from __future__ import annotations

from pathlib import Path
from typing import Mapping

from game_visual_forge.contracts import TileMapRequest
from game_visual_forge.processing.images import _load_pillow


def render_assembled_review_sheet(staging: Path, request: TileMapRequest, result_paths: Mapping[str, str]) -> str:
    Image = _load_pillow()
    from PIL import ImageDraw

    panels = []
    for label, relative in result_paths.items():
        if not relative:
            continue
        path = staging / relative
        if not path.is_file():
            continue
        try:
            with Image.open(path) as opened:
                image = opened.convert("RGBA")
                image.thumbnail((max(192, request.map_width * request.tile_width), max(144, request.map_height * request.tile_height)))
                panels.append((label, image.copy()))
        except OSError:
            continue
    if not panels:
        raise ValueError("assembled review sheet requires at least one readable artifact")
    panel_width = max(image.width for _, image in panels)
    panel_height = max(image.height for _, image in panels)
    columns = min(3, len(panels))
    rows = (len(panels) + columns - 1) // columns
    margin = 32
    gap = 16
    sheet = Image.new("RGBA", (columns * panel_width + (columns + 1) * gap, rows * (panel_height + margin) + (rows + 1) * gap), (232, 232, 232, 255))
    draw = ImageDraw.Draw(sheet)
    for index, (label, image) in enumerate(panels):
        column = index % columns
        row = index // columns
        x = gap + column * (panel_width + gap)
        y = gap + row * (panel_height + margin + gap)
        draw.text((x, y), label, fill=(20, 20, 20, 255))
        sheet.alpha_composite(image, (x, y + margin))
    output = staging / "assembled-review-sheet.png"
    sheet.save(output, format="PNG")
    return output.name
