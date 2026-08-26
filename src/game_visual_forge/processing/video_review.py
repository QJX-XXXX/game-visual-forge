from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from game_visual_forge.contracts.video_review import VideoMotionReview
from game_visual_forge.processing.video_probe import sha256_file


@dataclass(frozen=True)
class TemporalMetrics:
    frame_count: int
    exact_duplicate_rate: float
    near_duplicate_rate: float
    motion_coverage: float
    static_intervals: tuple[int, ...]
    subject_bounds_variation: float
    anchor_jitter: float
    first_last_loop_difference: float
    alpha_coverage: float
    clipping_risk: bool
    frame_flicker: float
    attention_reasons: tuple[str, ...]


def _difference(left: Any, right: Any) -> tuple[float, float]:
    from PIL import ImageChops, ImageStat
    diff = ImageChops.difference(left.convert("RGBA"), right.convert("RGBA"))
    mean = sum(ImageStat.Stat(diff).mean[:3]) / 3 / 255
    changed = sum(1 for pixel in diff.getdata() if pixel[:3] != (0, 0, 0)) / (diff.width * diff.height)
    return mean, changed


def calculate_temporal_metrics(frames: tuple[Any, ...]) -> TemporalMetrics:
    if not frames:
        raise ValueError("frames must not be empty")
    comparisons = tuple(_difference(left, right) for left, right in zip(frames, frames[1:]))
    exact = sum(1 for mean, _ in comparisons if mean == 0) / max(1, len(comparisons))
    near = sum(1 for mean, _ in comparisons if mean < 0.01) / max(1, len(comparisons))
    motion = sum(changed for _, changed in comparisons) / max(1, len(comparisons))
    static = tuple(index for index, (mean, _) in enumerate(comparisons) if mean == 0)
    bounds = [frame.convert("RGBA").getchannel("A").getbbox() for frame in frames]
    areas = [0 if bound is None else (bound[2] - bound[0]) * (bound[3] - bound[1]) for bound in bounds]
    max_area = max(areas) or 1
    variation = (max(areas) - min(areas)) / max_area
    anchors = [(0.0, 0.0) if bound is None else ((bound[0] + bound[2]) / 2, float(bound[3])) for bound in bounds]
    jitter = sum(abs(anchors[index][0] - anchors[index - 1][0]) + abs(anchors[index][1] - anchors[index - 1][1]) for index in range(1, len(anchors))) / max(1, len(anchors) - 1)
    loop_difference = _difference(frames[0], frames[-1])[0] if len(frames) > 1 else 0.0
    alpha = sum(1 for frame in frames for pixel in frame.convert("RGBA").getdata() if pixel[3] > 0) / sum(frame.width * frame.height for frame in frames)
    clipping = any(bound is not None and (bound[0] == 0 or bound[1] == 0 or bound[2] == frames[index].width or bound[3] == frames[index].height) for index, bound in enumerate(bounds))
    flicker = sum(abs(comparisons[index][0] - comparisons[index - 1][0]) for index in range(1, len(comparisons))) / max(1, len(comparisons) - 1)
    reasons = []
    if static:
        reasons.append("static-interval")
    if clipping:
        reasons.append("clipping-risk")
    if loop_difference > 0.2:
        reasons.append("loop-discontinuity")
    return TemporalMetrics(len(frames), exact, near, motion, static, variation, jitter, loop_difference, alpha, clipping, flicker, tuple(reasons))


def create_contact_sheet(frames: tuple[Any, ...], timestamps: tuple[float, ...], path: Path) -> Path:
    from PIL import Image, ImageDraw
    if len(frames) != len(timestamps):
        raise ValueError("timestamps must match frames")
    cell_width = max(frame.width for frame in frames)
    cell_height = max(frame.height for frame in frames) + 20
    columns = min(4, max(1, len(frames)))
    rows = (len(frames) + columns - 1) // columns
    sheet = Image.new("RGBA", (cell_width * columns, cell_height * rows), (32, 32, 32, 255))
    draw = ImageDraw.Draw(sheet)
    for index, frame in enumerate(frames):
        row, column = divmod(index, columns)
        sheet.alpha_composite(frame.convert("RGBA"), (column * cell_width, row * cell_height))
        draw.text((column * cell_width + 2, row * cell_height + frame.height + 2), f"{timestamps[index]:.3f}s", fill=(255, 255, 255, 255))
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, format="PNG", optimize=False)
    return path


def create_motion_difference(frames: tuple[Any, ...], path: Path) -> Path:
    from PIL import Image, ImageChops, ImageEnhance
    canvas = Image.new("RGBA", frames[0].size, (0, 0, 0, 255))
    for left, right in zip(frames, frames[1:]):
        diff = ImageChops.difference(left.convert("RGBA"), right.convert("RGBA")).convert("RGB")
        diff = ImageEnhance.Brightness(diff).enhance(3.0).convert("RGBA")
        canvas = ImageChops.lighter(canvas, diff)
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path, format="PNG", optimize=False)
    return path


def create_anchor_diagnostic(frames: tuple[Any, ...], path: Path, *, reference_bounds: tuple[int, int, int, int] | None = None) -> Path:
    from PIL import Image, ImageDraw
    width = max(frame.width for frame in frames)
    height = max(frame.height for frame in frames)
    canvas = Image.new("RGBA", (width, height), (20, 20, 20, 255))
    draw = ImageDraw.Draw(canvas)
    for index, frame in enumerate(frames):
        bound = frame.convert("RGBA").getchannel("A").getbbox()
        if bound is None:
            continue
        draw.rectangle(bound, outline=((index * 53) % 255, 220, 80, 255), width=1)
        draw.line(((bound[0] + bound[2]) / 2, bound[3], (bound[0] + bound[2]) / 2, height), fill=(255, 255, 255, 180), width=1)
    if reference_bounds is not None:
        draw.rectangle(reference_bounds, outline=(255, 80, 80, 255), width=2)
        center_x = (reference_bounds[0] + reference_bounds[2]) / 2
        draw.line((center_x, reference_bounds[3], center_x, height), fill=(255, 80, 80, 220), width=2)
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path, format="PNG", optimize=False)
    return path


def record_video_motion_review(repo_root: Path, request_fingerprint: str, source_sha256: str, quality_report_path: Path, artifact_paths: dict[str, Path], checks: dict[str, bool], approved: bool, reviewed_at: str) -> VideoMotionReview:
    root = repo_root.resolve()
    artifacts = {name: sha256_file(path) for name, path in artifact_paths.items()}
    review = VideoMotionReview.create(request_fingerprint=request_fingerprint, source_sha256=source_sha256, quality_report_sha256=sha256_file(quality_report_path), artifact_sha256=artifacts, checks=checks, approved=approved, reviewed_at=reviewed_at)
    return review


def validate_video_motion_review(repo_root: Path, review: VideoMotionReview, quality_report_path: Path, artifact_paths: dict[str, Path]) -> None:
    if sha256_file(quality_report_path) != review.quality_report_sha256:
        raise ValueError("review quality report hash is stale")
    for name, path in artifact_paths.items():
        if review.artifact_sha256.get(name) != sha256_file(path):
            raise ValueError("review artifact hash is stale")
    if not review.approved:
        raise ValueError("video motion review is not approved")
