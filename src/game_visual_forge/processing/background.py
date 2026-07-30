from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from game_visual_forge.contracts import BackgroundRemoval, SpriteRequest
from game_visual_forge.processing.images import _load_pillow


@dataclass(frozen=True)
class BackgroundResult:
    image: Any
    method: str
    needs_attention: bool


def remove_chroma(image: Any, color: str, *, tolerance: int = 0) -> Any:
    target = tuple(int(color[index:index + 2], 16) for index in (1, 3, 5))
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            red, green, blue, alpha = pixels[x, y]
            distance = (
                (red - target[0]) ** 2
                + (green - target[1]) ** 2
                + (blue - target[2]) ** 2
            )
            pixels[x, y] = (red, green, blue, 0 if distance <= tolerance ** 2 else alpha)
    return rgba


def _load_rembg() -> Any:
    try:
        from rembg import remove
    except ImportError:
        return None
    return remove


def remove_background(image: Any, request: SpriteRequest) -> BackgroundResult:
    if request.background_removal is BackgroundRemoval.REMBG:
        remove = _load_rembg()
        if remove is not None:
            return BackgroundResult(remove(image), "rembg", False)
        if request.chroma_color is not None:
            return BackgroundResult(remove_chroma(image, request.chroma_color), "chroma-fallback", True)
        return BackgroundResult(image.convert("RGBA"), "preserve-background", True)
    if request.background_removal is BackgroundRemoval.CHROMA:
        return BackgroundResult(remove_chroma(image, request.chroma_color or "#ff00ff"), "chroma", False)
    return BackgroundResult(image.convert("RGBA"), "preserve-background", True)
