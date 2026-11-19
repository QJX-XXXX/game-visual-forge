from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from decimal import Decimal, getcontext
from pathlib import Path
from typing import Any

from game_visual_forge.contracts.video import VideoFrameRecord, VideoSourceRecord
from game_visual_forge.errors import ErrorCode, ForgeError
from game_visual_forge.processing.video_probe import sha256_file


getcontext().prec = 28


@dataclass(frozen=True)
class SamplingPlan:
    start_seconds: float
    end_seconds: float
    loop: bool
    requested_counts: tuple[int, ...]
    extract_count: int
    timestamps: tuple[float, ...]
    indices_by_count: dict[int, tuple[int, ...]]


def sample_timestamps(start: float, end: float, count: int, *, loop: bool) -> tuple[float, ...]:
    if count <= 0:
        raise ValueError("count must be positive")
    if end <= start:
        raise ValueError("end must be greater than start")
    start_d = Decimal(str(start))
    span = Decimal(str(end)) - start_d
    if count == 1:
        return (float(start_d),)
    denominator = Decimal(count if loop else count - 1)
    return tuple(float(start_d + span * Decimal(index) / denominator) for index in range(count))


def derive_density_indices(highest_count: int, density: int) -> tuple[int, ...]:
    if highest_count <= 0 or density <= 0 or density > highest_count:
        raise ValueError("density must be within highest_count")
    if density == 1:
        return (0,)
    last = highest_count - 1
    return tuple((index * last) // (density - 1) for index in range(density))


def build_sampling_plan(start: float, end: float, requested_counts: tuple[int, ...], *, loop: bool) -> SamplingPlan:
    counts = tuple(sorted(set(int(item) for item in requested_counts)))
    if not counts or any(item <= 0 for item in counts):
        raise ValueError("requested_counts must contain positive values")
    highest = max(counts)
    return SamplingPlan(
        start_seconds=float(start), end_seconds=float(end), loop=loop,
        requested_counts=counts, extract_count=highest,
        timestamps=sample_timestamps(start, end, highest, loop=loop),
        indices_by_count={count: derive_density_indices(highest, count) for count in counts},
    )


def _argv(ffmpeg: Path, args: list[str]) -> list[str]:
    if ffmpeg.suffix.lower() == ".py":
        return [sys.executable, str(ffmpeg), *args]
    return [str(ffmpeg), *args]


def _rotation_filter(rotation: int) -> str | None:
    return {0: None, 90: "transpose=1", 180: "hflip,vflip", 270: "transpose=2"}[rotation]


def _extract_image(ffmpeg: Path, source: Path, target: Path, timestamp: float, rotation: int, *, last: bool = False) -> tuple[bool, bool]:
    target.unlink(missing_ok=True)
    args = ["-hide_banner", "-loglevel", "error", "-y", "-ss", f"{timestamp:.9f}", "-i", str(source), "-map", "0:v:0"]
    rotation_filter = _rotation_filter(rotation)
    if rotation_filter is not None:
        args.extend(["-vf", rotation_filter])
    # The image2 muxer replaces a single file as frames arrive, keeping memory
    # bounded when the last frame must be recovered from a sparse video stream.
    args.extend(["-vsync", "0", "-update", "1"] if last else ["-frames:v", "1"])
    result = subprocess.run(_argv(ffmpeg, [*args, str(target)]), capture_output=True, shell=False, check=False)
    written = target.is_file() and target.stat().st_size > 0
    return result.returncode == 0, written


def extract_highest_density(
    repo_root: Path,
    source: VideoSourceRecord,
    timestamps: tuple[float, ...],
    ffmpeg: Path,
    *,
    output_dir: str = "staging/raw-frames",
) -> tuple[VideoFrameRecord, ...]:
    root = repo_root.resolve()
    source_path = root / source.path
    target_root = root / output_dir
    target_root.mkdir(parents=True, exist_ok=True)
    records: list[VideoFrameRecord] = []
    last_frame: Path | None = None
    for index, timestamp in enumerate(timestamps):
        target = target_root / f"frame-{index:04d}.png"
        if last_frame is None or timestamp > source.duration_seconds:
            ok, written = _extract_image(ffmpeg, source_path, target, timestamp, source.display_rotation)
            if ok and not written and 0 <= timestamp <= source.duration_seconds:
                # A seek after the final presentation timestamp can exit 0
                # without emitting a frame, including a seek to the exact EOF.
                tail_start = max(0.0, timestamp - 1.0)
                ok, written = _extract_image(ffmpeg, source_path, target, tail_start, source.display_rotation, last=True)
                if ok and not written and tail_start > 0:
                    ok, written = _extract_image(ffmpeg, source_path, target, 0.0, source.display_rotation, last=True)
                if ok and written and all(later >= timestamp for later in timestamps[index + 1:]):
                    last_frame = target
        else:
            target.unlink(missing_ok=True)
            shutil.copyfile(last_frame, target)
            ok, written = True, True
        if not ok or not written:
            target.unlink(missing_ok=True)
            raise ForgeError(
                ErrorCode.PROCESSING_FAILED, f"FFmpeg failed to extract frame {index}",
                recoverable=True, context={"frame_index": index, "timestamp": timestamp},
            )
        records.append(VideoFrameRecord(1, index, float(timestamp), None, target.relative_to(root).as_posix(), None, None, sha256_file(target)))
    return tuple(records)


def derive_density_records(highest: tuple[VideoFrameRecord, ...], indices: tuple[int, ...]) -> tuple[VideoFrameRecord, ...]:
    return tuple(
        VideoFrameRecord(1, output_index, highest[index].source_timestamp, highest[index].source_frame_index, highest[index].raw_path, highest[index].clean_path, highest[index].delivery_path, highest[index].sha256)
        for output_index, index in enumerate(indices)
    )
