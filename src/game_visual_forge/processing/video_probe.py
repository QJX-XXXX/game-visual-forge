from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from game_visual_forge.contracts.provider import ExternalProvider
from game_visual_forge.contracts.video import VideoSourceRecord


@dataclass(frozen=True)
class VideoToolchain:
    ffmpeg: Path
    ffprobe: Path


@dataclass(frozen=True)
class ProbeMetadata:
    container: str
    video_codec: str
    width: int
    height: int
    display_rotation: int
    duration_seconds: float
    average_frame_rate: str | None
    real_frame_rate: str | None
    variable_frame_rate: bool
    frame_count: int | None
    audio_present: bool


def _resolve(value: str | Path | None, env_name: str, command: str, which: Callable[[str], str | None]) -> Path | None:
    if value is not None:
        return Path(value)
    configured = os.environ.get(env_name)
    if configured:
        return Path(configured)
    found = which(command)
    return None if found is None else Path(found)


def discover_toolchain(
    *,
    explicit_ffmpeg: str | Path | None = None,
    explicit_ffprobe: str | Path | None = None,
    which: Callable[[str], str | None] = shutil.which,
) -> VideoToolchain:
    ffmpeg = _resolve(explicit_ffmpeg, "GAME_VISUAL_FORGE_FFMPEG", "ffmpeg", which)
    ffprobe = _resolve(explicit_ffprobe, "GAME_VISUAL_FORGE_FFPROBE", "ffprobe", which)
    if ffmpeg is None or ffprobe is None:
        candidates = (
            Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "ffmpeg" / "bin",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages",
        )
        if ffmpeg is None:
            for directory in candidates:
                candidate = directory / "ffmpeg.exe"
                if candidate.is_file():
                    ffmpeg = candidate
                    break
        if ffprobe is None:
            for directory in candidates:
                candidate = directory / "ffprobe.exe"
                if candidate.is_file():
                    ffprobe = candidate
                    break
    if ffmpeg is None or ffprobe is None:
        raise FileNotFoundError("FFmpeg and FFprobe are required; install them manually or provide explicit paths")
    return VideoToolchain(ffmpeg=ffmpeg, ffprobe=ffprobe)


def _rational(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return None if text in {"", "0/0", "N/A"} else text


def _float(value: Any, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"invalid {field}") from error
    if result <= 0:
        raise ValueError(f"{field} must be positive")
    return result


def _rotation(stream: dict[str, Any]) -> int:
    raw = stream.get("tags", {}).get("rotate", 0)
    for side_data in stream.get("side_data_list", []):
        if "rotation" in side_data:
            raw = side_data["rotation"]
    try:
        value = int(float(raw)) % 360
    except (TypeError, ValueError) as error:
        raise ValueError("invalid display rotation") from error
    if value not in {0, 90, 180, 270}:
        raise ValueError("display rotation must be 0, 90, 180, or 270")
    return value


def parse_ffprobe_json(value: dict[str, Any]) -> ProbeMetadata:
    streams = value.get("streams")
    if not isinstance(streams, list):
        raise ValueError("ffprobe streams must be an array")
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    if video is None:
        raise ValueError("video stream is required")
    width = int(video.get("width", 0))
    height = int(video.get("height", 0))
    if width <= 0 or height <= 0:
        raise ValueError("video dimensions must be positive")
    rotation = _rotation(video)
    display_width, display_height = (height, width) if rotation in {90, 270} else (width, height)
    format_data = value.get("format") or {}
    duration = _float(video.get("duration", format_data.get("duration")), "duration")
    average = _rational(video.get("avg_frame_rate"))
    real = _rational(video.get("r_frame_rate"))
    frame_count = video.get("nb_frames")
    try:
        frame_count_value = None if frame_count in (None, "N/A") else int(frame_count)
    except (TypeError, ValueError) as error:
        raise ValueError("invalid frame count") from error
    if frame_count_value is not None and frame_count_value <= 0:
        frame_count_value = None
    return ProbeMetadata(
        container=str(format_data.get("format_name", "unknown")).split(",")[0],
        video_codec=str(video.get("codec_name", "unknown")),
        width=display_width,
        height=display_height,
        display_rotation=rotation,
        duration_seconds=duration,
        average_frame_rate=average,
        real_frame_rate=real,
        variable_frame_rate=average is not None and real is not None and average != real,
        frame_count=frame_count_value,
        audio_present=any(stream.get("codec_type") == "audio" for stream in streams),
    )


def validate_trim(start: float, end: float | None, duration: float) -> tuple[float, float]:
    if start < 0 or start >= duration:
        raise ValueError("clip_start_seconds must be within source duration")
    resolved_end = duration if end is None else end
    if resolved_end <= start or resolved_end > duration:
        raise ValueError("clip_end_seconds must be greater than clip_start_seconds and within duration")
    return float(start), float(resolved_end)


def _run_ffprobe(ffprobe: Path, source: Path) -> dict[str, Any]:
    argv = [sys.executable, str(ffprobe), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(source)] if ffprobe.suffix.lower() == ".py" else [str(ffprobe), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(source)]
    result = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", shell=False, check=False)
    if result.returncode != 0:
        raise ValueError("ffprobe could not decode source video")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ValueError("ffprobe returned invalid JSON") from error
    if not isinstance(payload, dict):
        raise ValueError("ffprobe returned an invalid object")
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ingest_video(
    repo_root: Path,
    source_path: Path,
    request_fingerprint: str,
    ffprobe: Path | None = None,
    *,
    toolchain: VideoToolchain | None = None,
    clip_start_seconds: float = 0.0,
    clip_end_seconds: float | None = None,
    provider: ExternalProvider | None = None,
    backend: str | None = None,
    model: str | None = None,
) -> VideoSourceRecord:
    root = repo_root.resolve()
    source = source_path.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    try:
        relative = source.relative_to(root).as_posix()
    except ValueError as error:
        raise ValueError("source video must be inside repository root") from error
    probe_path = ffprobe or (toolchain.ffprobe if toolchain is not None else discover_toolchain().ffprobe)
    metadata = parse_ffprobe_json(_run_ffprobe(Path(probe_path), source))
    validate_trim(clip_start_seconds, clip_end_seconds, metadata.duration_seconds)
    return VideoSourceRecord(
        schema_version=1, path=relative, sha256=sha256_file(source), container=metadata.container,
        video_codec=metadata.video_codec, width=metadata.width, height=metadata.height,
        display_rotation=metadata.display_rotation, duration_seconds=metadata.duration_seconds,
        average_frame_rate=metadata.average_frame_rate, real_frame_rate=metadata.real_frame_rate,
        variable_frame_rate=metadata.variable_frame_rate, frame_count=metadata.frame_count,
        audio_present=metadata.audio_present, request_fingerprint=request_fingerprint,
        provider=provider, backend=backend, model=model,
    )
