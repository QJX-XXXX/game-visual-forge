from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any


def _smoothstep(value: Any, low: float, high: float) -> Any:
    import numpy as np

    normalized = np.clip((value - low) / (high - low), 0.0, 1.0)
    return normalized * normalized * (3.0 - 2.0 * normalized)


def _target_rgb(color: str) -> Any:
    import numpy as np

    return np.asarray(
        [int(color[index:index + 2], 16) for index in (1, 3, 5)],
        dtype=np.float32,
    ) / 255.0


def _is_magenta_key(target: Any) -> bool:
    return bool(target[0] >= 0.75 and target[2] >= 0.75 and target[1] <= 0.25)


def _chroma_foreground_score(rgb: Any, target: Any) -> Any:
    import numpy as np

    pixel_scale = np.max(rgb, axis=2)
    normalized_rgb = rgb / np.maximum(pixel_scale[:, :, None], 1.0 / 255.0)
    normalized_target = target / max(float(np.max(target)), 1.0 / 255.0)
    distance = np.linalg.norm(normalized_rgb - normalized_target, axis=2)
    return _smoothstep(distance, 0.10, 0.58)


def _nearest_foreground_colors(
    rgb: Any,
    alpha: Any,
    *,
    extra_safe: Any | None = None,
) -> Any:
    import numpy as np
    from scipy import ndimage

    safe = alpha >= 0.92
    if extra_safe is not None:
        safe &= extra_safe
    if not np.any(safe):
        return rgb
    _, nearest = ndimage.distance_transform_edt(
        ~safe,
        return_indices=True,
    )
    return rgb[nearest[0], nearest[1]]


def _repair_magenta_key_inversion(
    raw_rgb: Any,
    foreground: Any,
    alpha: Any,
) -> Any:
    import numpy as np

    raw_magenta_excess = np.clip(
        np.minimum(raw_rgb[:, :, 0], raw_rgb[:, :, 2]) - raw_rgb[:, :, 1],
        0.0,
        1.0,
    )
    raw_magenta_confidence = _smoothstep(raw_magenta_excess, 0.01, 0.16)
    donor = _nearest_foreground_colors(
        raw_rgb,
        alpha,
        extra_safe=raw_magenta_confidence <= 0.05,
    )

    output_magenta_excess = np.clip(
        np.minimum(foreground[:, :, 0], foreground[:, :, 2])
        - foreground[:, :, 1],
        0.0,
        1.0,
    )
    output_green_excess = np.clip(
        foreground[:, :, 1]
        - np.maximum(foreground[:, :, 0], foreground[:, :, 2]),
        0.0,
        1.0,
    )
    artifact_strength = _smoothstep(
        np.maximum(output_magenta_excess, output_green_excess),
        0.02,
        0.24,
    )
    donor_weight = np.clip(
        raw_magenta_confidence * np.maximum(artifact_strength, 0.78),
        0.0,
        0.99,
    )
    corrected = (
        foreground * (1.0 - donor_weight[:, :, None])
        + donor * donor_weight[:, :, None]
    )
    green_limit = np.maximum(corrected[:, :, 0], corrected[:, :, 2]) + 0.018
    limited_green = np.minimum(corrected[:, :, 1], green_limit)
    corrected[:, :, 1] = (
        corrected[:, :, 1] * (1.0 - raw_magenta_confidence)
        + limited_green * raw_magenta_confidence
    )
    return corrected


def hybrid_chroma_fusion(
    raw_image: Any,
    semantic_image: Any,
    color: str,
) -> Any:
    import numpy as np
    from PIL import Image
    from scipy import ndimage

    raw_rgb = np.asarray(raw_image.convert("RGB"), dtype=np.float32) / 255.0
    semantic_rgba = np.asarray(
        semantic_image.convert("RGBA"),
        dtype=np.uint8,
    )
    semantic_alpha = semantic_rgba[:, :, 3].astype(np.float32) / 255.0
    target = _target_rgb(color)
    chroma_foreground = _chroma_foreground_score(raw_rgb, target)

    semantic_foreground = semantic_alpha > (2.0 / 255.0)
    distance_inside = ndimage.distance_transform_edt(semantic_foreground)
    edge_weight = np.clip(1.0 - distance_inside / 44.0, 0.0, 1.0)

    if _is_magenta_key(target):
        key_excess = np.clip(
            np.minimum(raw_rgb[:, :, 0], raw_rgb[:, :, 2])
            - raw_rgb[:, :, 1],
            0.0,
            1.0,
        )
        key_strength = _smoothstep(key_excess, 0.025, 0.35)
        key_candidate = key_excess >= 0.055
        global_high_confidence = (
            _smoothstep(key_excess, 0.40, 0.80)
            * (1.0 - chroma_foreground)
        )
    else:
        key_strength = 1.0 - chroma_foreground
        key_candidate = chroma_foreground <= 0.45
        global_high_confidence = _smoothstep(
            1.0 - chroma_foreground,
            0.80,
            0.98,
        )

    border_seed = np.zeros_like(key_candidate)
    border_seed[0, :] = key_candidate[0, :]
    border_seed[-1, :] = key_candidate[-1, :]
    border_seed[:, 0] = key_candidate[:, 0]
    border_seed[:, -1] = key_candidate[:, -1]
    connected_key = ndimage.binary_propagation(
        border_seed,
        mask=key_candidate,
    )
    distance_from_connected = ndimage.distance_transform_edt(~connected_key)
    connected_influence = np.clip(
        1.0 - distance_from_connected / 10.0,
        0.0,
        1.0,
    ) * key_strength
    edge_key_background = edge_weight * (1.0 - chroma_foreground)
    background_confidence = np.maximum(
        np.maximum(connected_influence, edge_key_background),
        global_high_confidence,
    )

    fused_alpha = semantic_alpha * (1.0 - background_confidence)
    exact_distance = np.linalg.norm(raw_rgb - target, axis=2)
    fused_alpha[exact_distance <= (32.0 / 255.0)] = 0.0
    fused_alpha[fused_alpha < (2.0 / 255.0)] = 0.0

    safe_foreground = (
        (semantic_alpha >= 0.90)
        & (chroma_foreground >= 0.82)
        & (background_confidence <= 0.05)
        & (distance_inside >= 3.0)
    )
    donor = _nearest_foreground_colors(
        raw_rgb,
        semantic_alpha,
        extra_safe=safe_foreground,
    )
    contamination = np.maximum(
        background_confidence,
        np.maximum(edge_weight * key_strength, key_strength * 0.96),
    )
    contamination = np.clip(contamination, 0.0, 0.95)
    corrected_rgb = (
        raw_rgb * (1.0 - contamination[:, :, None])
        + donor * contamination[:, :, None]
    )

    output = np.empty((*fused_alpha.shape, 4), dtype=np.uint8)
    output[:, :, :3] = np.clip(
        np.rint(corrected_rgb * 255.0),
        0,
        255,
    ).astype(np.uint8)
    output[:, :, 3] = np.clip(
        np.rint(fused_alpha * 255.0),
        0,
        255,
    ).astype(np.uint8)
    return Image.fromarray(output, mode="RGBA")


def reconstruct_known_background(
    raw_image: Any,
    hybrid_image: Any,
    color: str,
) -> Any:
    import numpy as np
    from PIL import Image

    raw_rgb = np.asarray(raw_image.convert("RGB"), dtype=np.float32) / 255.0
    hybrid_rgba = np.asarray(hybrid_image.convert("RGBA"), dtype=np.uint8)
    alpha = hybrid_rgba[:, :, 3].astype(np.float32) / 255.0
    target = _target_rgb(color)
    donor = _nearest_foreground_colors(raw_rgb, alpha)

    denominator = np.maximum(alpha[:, :, None], 0.035)
    foreground = (
        raw_rgb - (1.0 - alpha[:, :, None]) * target
    ) / denominator
    invalid_amount = np.max(
        np.maximum(-foreground, foreground - 1.0),
        axis=2,
    )
    foreground = np.clip(foreground, 0.0, 1.0)
    unstable = np.clip((0.16 - alpha) / 0.13, 0.0, 1.0)
    out_of_gamut = np.clip(invalid_amount * 3.0, 0.0, 1.0)
    donor_weight = np.maximum(unstable, out_of_gamut)
    foreground = (
        foreground * (1.0 - donor_weight[:, :, None])
        + donor * donor_weight[:, :, None]
    )
    if _is_magenta_key(target):
        foreground = _repair_magenta_key_inversion(
            raw_rgb,
            foreground,
            alpha,
        )

    output = np.empty((*alpha.shape, 4), dtype=np.uint8)
    output[:, :, :3] = np.clip(
        np.rint(foreground * 255.0),
        0,
        255,
    ).astype(np.uint8)
    output[:, :, 3] = hybrid_rgba[:, :, 3]
    return Image.fromarray(output, mode="RGBA")


def _subject_crop(alpha: Any, margin: int = 36) -> tuple[int, int, int, int]:
    import numpy as np

    ys, xs = np.where(alpha > (2.0 / 255.0))
    if len(xs) == 0:
        return 0, 0, alpha.shape[1], alpha.shape[0]
    return (
        max(int(xs.min()) - margin, 0),
        max(int(ys.min()) - margin, 0),
        min(int(xs.max()) + margin + 1, alpha.shape[1]),
        min(int(ys.max()) + margin + 1, alpha.shape[0]),
    )


def _trimap_from_alpha(alpha: Any, raw_rgb: Any, target: Any) -> Any:
    import numpy as np
    from scipy import ndimage

    subject = alpha >= 0.45
    sure_foreground = ndimage.binary_erosion(
        subject,
        iterations=3,
        border_value=0,
    )
    sure_background = ~ndimage.binary_dilation(
        subject,
        iterations=7,
        border_value=0,
    )
    exact_key = np.linalg.norm(raw_rgb - target, axis=2) <= (32.0 / 255.0)
    sure_background |= exact_key

    trimap = np.full(alpha.shape, 0.5, dtype=np.float64)
    trimap[sure_background] = 0.0
    trimap[sure_foreground] = 1.0
    return trimap


def refine_with_pymatting(
    raw_image: Any,
    hybrid_image: Any,
    color: str,
) -> Any:
    import numpy as np
    from PIL import Image
    from scipy import ndimage

    cache_dir = Path(tempfile.gettempdir()) / "game-visual-forge-numba-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("NUMBA_CACHE_DIR", str(cache_dir))
    from pymatting import estimate_alpha_cf, estimate_foreground_ml

    raw_rgb = np.asarray(raw_image.convert("RGB"), dtype=np.float64) / 255.0
    hybrid_rgba = np.asarray(hybrid_image.convert("RGBA"), dtype=np.uint8)
    seed_alpha = hybrid_rgba[:, :, 3].astype(np.float64) / 255.0
    target = _target_rgb(color).astype(np.float64)
    x0, y0, x1, y1 = _subject_crop(seed_alpha)
    crop_rgb = raw_rgb[y0:y1, x0:x1]
    crop_seed_alpha = seed_alpha[y0:y1, x0:x1]
    trimap = _trimap_from_alpha(crop_seed_alpha, crop_rgb, target)

    crop_alpha = estimate_alpha_cf(
        crop_rgb,
        trimap,
        laplacian_kwargs={"epsilon": 1e-6, "radius": 1},
        cg_kwargs={"maxiter": 500, "rtol": 1e-5},
    )
    crop_alpha = np.minimum(
        crop_alpha,
        ndimage.maximum_filter(crop_seed_alpha, size=3),
    )
    crop_foreground = estimate_foreground_ml(
        crop_rgb,
        crop_alpha,
        regularization=1e-5,
        n_small_iterations=5,
        n_big_iterations=1,
        gradient_weight=1.0,
    )
    crop_foreground = np.clip(crop_foreground, 0.0, 1.0)
    if _is_magenta_key(target):
        crop_foreground = _repair_magenta_key_inversion(
            crop_rgb,
            crop_foreground,
            crop_alpha,
        )

    output_rgb = np.zeros_like(raw_rgb, dtype=np.float64)
    output_alpha = np.zeros(seed_alpha.shape, dtype=np.float64)
    output_rgb[y0:y1, x0:x1] = crop_foreground
    output_alpha[y0:y1, x0:x1] = np.clip(crop_alpha, 0.0, 1.0)

    output = np.empty((*output_alpha.shape, 4), dtype=np.uint8)
    output[:, :, :3] = np.clip(
        np.rint(output_rgb * 255.0),
        0,
        255,
    ).astype(np.uint8)
    output[:, :, 3] = np.clip(
        np.rint(output_alpha * 255.0),
        0,
        255,
    ).astype(np.uint8)
    return Image.fromarray(output, mode="RGBA")


def measure_chroma_residue(
    image: Any,
    color: str,
    *,
    alpha_threshold: int = 8,
    brightness_threshold: int = 16,
    distance_threshold: float = 0.5,
) -> dict[str, float | int]:
    import numpy as np

    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    rgb = rgba[:, :, :3].astype(np.float32)
    alpha = rgba[:, :, 3]
    target = _target_rgb(color) * 255.0
    pixel_scale = np.max(rgb, axis=2)
    normalized_rgb = rgb / np.maximum(pixel_scale[:, :, None], 1.0)
    normalized_target = target / max(float(np.max(target)), 1.0)
    chroma_distance = np.linalg.norm(
        normalized_rgb - normalized_target,
        axis=2,
    )
    residue = (
        (alpha >= alpha_threshold)
        & (pixel_scale >= brightness_threshold)
        & (chroma_distance < distance_threshold)
    )
    visible = alpha >= alpha_threshold
    residue_pixels = int(residue.sum())
    visible_pixels = int(visible.sum())
    return {
        "pixels": residue_pixels,
        "visible_pixels": visible_pixels,
        "pixel_ratio_percent": round(
            100.0 * residue_pixels / visible_pixels,
            4,
        )
        if visible_pixels
        else 0.0,
        "alpha_mass": round(float(alpha[residue].sum()) / 255.0, 1),
    }
