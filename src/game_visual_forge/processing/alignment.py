from __future__ import annotations

from typing import Any

from game_visual_forge.processing.images import _load_pillow


def align_bottom_center(frames: tuple[Any, ...]) -> tuple[Any, ...]:
    if not frames:
        return ()
    width = max(frame.width for frame in frames)
    height = max(frame.height for frame in frames)
    Image = _load_pillow()
    aligned = []
    for frame in frames:
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        x = (width - frame.width) // 2
        y = height - frame.height
        canvas.alpha_composite(frame.convert("RGBA"), (x, y))
        aligned.append(canvas)
    return tuple(aligned)
