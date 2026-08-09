from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from game_visual_forge.contracts.serialization import dump_json
from game_visual_forge.contracts.video import (
    VideoAnchor,
    VideoBackgroundMode,
    VideoFrameRecord,
    VideoOutput,
    VideoProcessingMode,
    VideoProcessingResult,
    VideoSpriteRequest,
    VideoSourceRecord,
)
from game_visual_forge.processing.background import BackgroundResult, remove_background, remove_chroma
from game_visual_forge.processing.frames import trim_alpha
from game_visual_forge.processing.images import _load_pillow
from game_visual_forge.processing.video_probe import sha256_file


def _video_background(image: Any, request: VideoSpriteRequest, remover: Callable[[Any, VideoSpriteRequest], Any] | None) -> tuple[Any, str, bool]:
    if request.background_mode is VideoBackgroundMode.PRESERVE:
        return image.convert("RGBA"), "preserve-background", False
    if request.background_mode is VideoBackgroundMode.CHROMA:
        return remove_chroma(image, request.chroma_color or "#ff00ff"), "chroma", False
    if remover is not None:
        value = remover(image, request)
        if isinstance(value, BackgroundResult):
            return value.image, value.method, value.needs_attention
        cleaned, method, attention = value
        return cleaned, str(method), bool(attention)
    adapter = SimpleNamespace(
        background_removal=__import__("game_visual_forge.contracts", fromlist=["BackgroundRemoval"]).BackgroundRemoval.REMBG,
        chroma_color=request.chroma_color,
        rembg_refinement=None,
    )
    result = remove_background(image, adapter)
    return result.image, result.method, result.needs_attention


def _delivery_frames(frames: tuple[Any, ...], request: VideoSpriteRequest) -> tuple[tuple[Any, ...], float, tuple[tuple[int, int, int, int], ...]]:
    if not frames:
        return (), 1.0, ()
    bounds = tuple(frame.convert("RGBA").getchannel("A").getbbox() for frame in frames)
    if any(bound is None for bound in bounds):
        raise ValueError("video frame has no visible content")
    typed_bounds = tuple(bound for bound in bounds if bound is not None)
    max_width = max(right - left for left, _, right, _ in typed_bounds)
    max_height = max(bottom - top for _, top, _, bottom in typed_bounds)
    canvas_width = request.canvas_width or max_width
    canvas_height = request.canvas_height or max_height
    scale = min(canvas_width * request.fit_scale / max_width, canvas_height * request.fit_scale / max_height)
    Image = _load_pillow()
    resampling = Image.Resampling.NEAREST if request.processing_mode is VideoProcessingMode.PIXEL else Image.Resampling.LANCZOS
    result = []
    for frame, (left, top, right, bottom) in zip(frames, typed_bounds, strict=True):
        cropped = frame.convert("RGBA").crop((left, top, right, bottom))
        width = max(1, round(cropped.width * scale))
        height = max(1, round(cropped.height * scale))
        scaled = cropped.resize((width, height), resample=resampling)
        canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))
        x = (canvas_width - width) // 2
        if request.anchor is VideoAnchor.FEET:
            bottom_margin = round(canvas_height * (1 - request.fit_scale) / 2)
            y = canvas_height - bottom_margin - height
        else:
            y = (canvas_height - height) // 2
        canvas.alpha_composite(scaled, (x, y))
        result.append(canvas)
    return tuple(result), scale, typed_bounds


def _write_frames(frames: tuple[Any, ...], directory: Path) -> tuple[Path, ...]:
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for index, frame in enumerate(frames):
        path = directory / f"frame-{index:03d}.png"
        frame.save(path, format="PNG", optimize=False)
        paths.append(path)
    return tuple(paths)


def _write_strip(frames: tuple[Any, ...], path: Path) -> Path:
    Image = _load_pillow()
    strip = Image.new("RGBA", (sum(frame.width for frame in frames), max(frame.height for frame in frames)), (0, 0, 0, 0))
    x = 0
    for frame in frames:
        strip.alpha_composite(frame, (x, 0))
        x += frame.width
    path.parent.mkdir(parents=True, exist_ok=True)
    strip.save(path, format="PNG", optimize=False)
    return path


def _write_sheet(frames: tuple[Any, ...], path: Path) -> Path:
    Image = _load_pillow()
    columns = max(1, math.ceil(math.sqrt(len(frames))))
    rows = math.ceil(len(frames) / columns)
    sheet = Image.new("RGBA", (frames[0].width * columns, frames[0].height * rows), (0, 0, 0, 0))
    for index, frame in enumerate(frames):
        row, column = divmod(index, columns)
        sheet.alpha_composite(frame, (column * frames[0].width, row * frames[0].height))
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, format="PNG", optimize=False)
    return path


def _write_gif(frames: tuple[Any, ...], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    converted = [frame.convert("P", palette=0) for frame in frames]
    converted[0].save(path, format="GIF", save_all=True, append_images=converted[1:], duration=100, loop=0, disposal=2)
    return path


def process_video_sprite(
    repo_root: Path,
    request: VideoSpriteRequest,
    source: VideoSourceRecord,
    raw_frames: tuple[VideoFrameRecord, ...],
    *,
    frame_counts: tuple[int, ...] | None = None,
    remover: Callable[[Any, VideoSpriteRequest], Any] | None = None,
) -> VideoProcessingResult:
    Image = _load_pillow()
    root = repo_root.resolve()
    highest = max(frame_counts or request.frame_counts)
    if len(raw_frames) != highest:
        raise ValueError(f"raw frame count must equal highest requested density {highest}")
    output_dir = root / request.output_dir
    staging = output_dir.parent / f".{output_dir.name}.staging-{source.sha256[:12]}"
    staging.mkdir(parents=True, exist_ok=True)
    source_images = []
    for record in raw_frames:
        path = root / record.raw_path
        with Image.open(path) as opened:
            source_images.append(opened.convert("RGBA"))
    cleaned = []
    methods: list[str] = []
    needs_attention = False
    reasons: list[str] = []
    for image in source_images:
        background, method, attention = _video_background(image, request, remover)
        methods.append(method)
        needs_attention = needs_attention or attention
        if attention and "background-removal-failed" not in reasons:
            reasons.append("background-removal-failed")
        try:
            cleaned.append(trim_alpha(background))
        except Exception:
            needs_attention = True
            reasons.append("empty-clean-frame")
    if not cleaned:
        return VideoProcessingResult(1, request.asset_id, source.request_fingerprint, staging.relative_to(root).as_posix(), (), {}, "frame-timing.json", tuple(methods), True, tuple(reasons))
    delivery, scale, bounds = _delivery_frames(tuple(cleaned), request)
    requested = tuple(sorted(set(frame_counts or request.frame_counts)))
    artifacts: dict[str, str] = {}
    all_records: list[VideoFrameRecord] = []
    timing: list[dict[str, Any]] = []
    for density in requested:
        indices = tuple((index * (highest - 1)) // (density - 1) for index in range(density)) if density > 1 else (0,)
        density_frames = tuple(delivery[index] for index in indices)
        frame_paths = _write_frames(density_frames, staging / "delivery" / "frames" / str(density)) if VideoOutput.FRAMES in request.outputs else ()
        if frame_paths:
            artifacts[f"frames:{density}"] = frame_paths[0].parent.relative_to(root).as_posix()
        if VideoOutput.STRIPS in request.outputs:
            strip = _write_strip(density_frames, staging / "delivery" / "strips" / f"density-{density}.png")
            artifacts[f"strips:{density}"] = strip.relative_to(root).as_posix()
        if VideoOutput.SHEETS in request.outputs:
            sheet = _write_sheet(density_frames, staging / "delivery" / "sheets" / f"density-{density}.png")
            artifacts[f"sheets:{density}"] = sheet.relative_to(root).as_posix()
        if VideoOutput.GIF in request.outputs:
            gif = _write_gif(density_frames, staging / "delivery" / "previews" / f"density-{density}.gif")
            artifacts[f"gif:{density}"] = gif.relative_to(root).as_posix()
        for output_index, source_index in enumerate(indices):
            timing.append({"density": density, "output_index": output_index, "source_timestamp": raw_frames[source_index].source_timestamp, "source_index": source_index})
        if density == highest and frame_paths:
            for index, path in enumerate(frame_paths):
                all_records.append(VideoFrameRecord(1, index, raw_frames[index].source_timestamp, raw_frames[index].source_frame_index, raw_frames[index].raw_path, None, path.relative_to(root).as_posix(), sha256_file(path)))
    timing_path = staging / "frame-timing.json"
    dump_json(timing_path, {"schema_version": 1, "loop": request.loop, "frames": timing, "scale": scale, "source_bounds": [list(item) for item in bounds], "cleanup_methods": methods})
    return VideoProcessingResult(1, request.asset_id, source.request_fingerprint, staging.relative_to(root).as_posix(), tuple(all_records), artifacts, timing_path.relative_to(root).as_posix(), tuple(methods), needs_attention, tuple(dict.fromkeys(reasons)))
