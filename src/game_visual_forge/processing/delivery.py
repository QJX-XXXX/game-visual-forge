from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from game_visual_forge.contracts import DeliveryAnchor, DeliveryNormalization
from game_visual_forge.errors import ErrorCode, ForgeError
from game_visual_forge.processing.images import _load_pillow


@dataclass(frozen=True)
class DeliveryNormalizationResult:
    frames: tuple[Any, ...]
    source_bounds: tuple[tuple[int, int, int, int], ...]
    scale: float


def normalize_delivery_frames(
    frames: tuple[Any, ...],
    config: DeliveryNormalization,
) -> DeliveryNormalizationResult:
    if not frames:
        return DeliveryNormalizationResult((), (), 1.0)
    bounds = []
    for frame in frames:
        bound = frame.convert("RGBA").getchannel("A").getbbox()
        if bound is None:
            raise ForgeError(
                ErrorCode.INVALID_FRAME,
                "cannot normalize an empty sprite frame",
                recoverable=True,
            )
        bounds.append(bound)
    max_width = max(right - left for left, _, right, _ in bounds)
    max_height = max(bottom - top for _, top, _, bottom in bounds)
    scale = min(
        config.canvas_width * float(config.fit_scale) / max_width,
        config.canvas_height * float(config.fit_scale) / max_height,
    )
    Image = _load_pillow()
    normalized = []
    for frame, (left, top, right, bottom) in zip(frames, bounds, strict=True):
        cropped = frame.convert("RGBA").crop((left, top, right, bottom))
        width = max(1, round(cropped.width * scale))
        height = max(1, round(cropped.height * scale))
        scaled = cropped.resize((width, height), Image.Resampling.LANCZOS)
        canvas = Image.new(
            "RGBA",
            (config.canvas_width, config.canvas_height),
            (0, 0, 0, 0),
        )
        x = (config.canvas_width - width) // 2
        if config.anchor is DeliveryAnchor.FEET:
            bottom_margin = round(config.canvas_height * (1 - float(config.fit_scale)) / 2)
            y = config.canvas_height - bottom_margin - height
        else:
            y = (config.canvas_height - height) // 2
        canvas.alpha_composite(scaled, (x, y))
        normalized.append(canvas)
    return DeliveryNormalizationResult(tuple(normalized), tuple(bounds), scale)
