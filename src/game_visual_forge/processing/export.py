from __future__ import annotations

from pathlib import Path
from typing import Any

from game_visual_forge.contracts import SpriteLayout, SpriteOutput, SpriteRequest
from game_visual_forge.processing.images import _load_pillow


def export_frames(frames: tuple[Any, ...], output_dir: Path) -> tuple[Path, ...]:
    frame_dir = output_dir / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for index, frame in enumerate(frames):
        path = frame_dir / f"frame-{index:03d}.png"
        frame.save(path, format="PNG", optimize=False)
        paths.append(path)
    return tuple(paths)


def export_sheet(frames: tuple[Any, ...], request: SpriteRequest, output_dir: Path) -> Path | None:
    if SpriteOutput.SHEET not in request.outputs:
        return None
    Image = _load_pillow()
    cell_width = max(frame.width for frame in frames)
    cell_height = max(frame.height for frame in frames)
    sheet = Image.new("RGBA", (cell_width * request.grid_columns, cell_height * request.grid_rows), (0, 0, 0, 0))
    for index, frame in enumerate(frames):
        row, column = divmod(index, request.grid_columns)
        sheet.alpha_composite(frame, (column * cell_width, row * cell_height))
    path = output_dir / "sprite-sheet.png"
    sheet.save(path, format="PNG", optimize=False)
    return path


def export_gif(frames: tuple[Any, ...], request: SpriteRequest, output_dir: Path) -> Path | None:
    if SpriteOutput.GIF not in request.outputs:
        return None
    path = output_dir / "preview.gif"
    converted = [frame.convert("P", palette=0) for frame in frames]
    converted[0].save(path, format="GIF", save_all=True, append_images=converted[1:], duration=100, loop=0, disposal=2, transparency=0)
    return path
