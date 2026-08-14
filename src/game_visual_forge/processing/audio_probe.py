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

from game_visual_forge.contracts.audio import AudioGenerationMode, AudioRequest, AudioSourceRecord
from game_visual_forge.jobs.fingerprints import fingerprint_request


@dataclass(frozen=True)
class AudioToolchain:
    ffmpeg: Path
    ffprobe: Path


@dataclass(frozen=True)
class AudioProbeMetadata:
    codec_name: str
    sample_rate: int
    channels: int
    channel_layout: str | None
    sample_format: str
    duration_seconds: float


def discover_audio_toolchain(
    explicit_ffmpeg: str | Path | None = None,
    explicit_ffprobe: str | Path | None = None,
    which: Callable[[str], str | None] = shutil.which,
) -> AudioToolchain:
    ffmpeg_value = explicit_ffmpeg or os.environ.get("GAME_VISUAL_FORGE_FFMPEG") or which("ffmpeg")
    ffprobe_value = explicit_ffprobe or os.environ.get("GAME_VISUAL_FORGE_FFPROBE") or which("ffprobe")
    if not ffmpeg_value or not ffprobe_value:
        raise FileNotFoundError("FFmpeg and FFprobe are required")
    return AudioToolchain(Path(ffmpeg_value), Path(ffprobe_value))


def parse_audio_ffprobe_json(value: dict[str, Any]) -> AudioProbeMetadata:
    streams = [item for item in value.get("streams", []) if item.get("codec_type") == "audio"]
    if len(streams) != 1:
        raise ValueError("exactly one audio stream is required")
    stream = streams[0]
    codec = str(stream.get("codec_name") or "")
    sample_format = str(stream.get("sample_fmt") or "")
    sample_rate = int(stream.get("sample_rate") or 0)
    channels = int(stream.get("channels") or 0)
    duration = float((stream.get("duration") or value.get("format", {}).get("duration") or 0))
    if not codec or not sample_format or sample_rate <= 0 or channels not in {1, 2} or duration <= 0:
        raise ValueError("audio probe metadata is invalid")
    return AudioProbeMetadata(codec, sample_rate, channels, stream.get("channel_layout"), sample_format, duration)


def _probe(ffprobe: Path, source: Path) -> AudioProbeMetadata:
    argv = ([sys.executable, str(ffprobe)] if ffprobe.suffix.lower() == ".py" else [str(ffprobe)]) + ["-v", "error", "-select_streams", "a:0", "-show_streams", "-show_format", "-of", "json", str(source)]
    completed = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="strict", shell=False, check=False)
    if completed.returncode != 0:
        raise ValueError("FFprobe failed")
    return parse_audio_ffprobe_json(json.loads(completed.stdout))


def ingest_audio(
    repo_root: Path,
    source_path: Path,
    request: AudioRequest,
    request_fingerprint: str,
    ffprobe: Path | None = None,
    toolchain: AudioToolchain | None = None,
) -> AudioSourceRecord:
    root = repo_root.resolve()
    source = source_path.resolve()
    try:
        relative = source.relative_to(root).as_posix()
    except ValueError as error:
        raise ValueError("source must be inside repository root") from error
    if not source.is_file():
        raise FileNotFoundError(source)
    probe_path = ffprobe or (toolchain.ffprobe if toolchain else discover_audio_toolchain().ffprobe)
    metadata = _probe(Path(probe_path), source)
    if request.mode is AudioGenerationMode.INPAINT:
        if request.edit_end_seconds is None or request.edit_end_seconds > metadata.duration_seconds:
            raise ValueError("inpaint edit bounds must be inside source duration")
    if request.mode is AudioGenerationMode.CONTINUE and request.duration_seconds <= metadata.duration_seconds:
        raise ValueError("continue target duration must be greater than source duration")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    return AudioSourceRecord(1, relative, digest, metadata.codec_name, metadata.sample_rate, metadata.channels, metadata.channel_layout, metadata.sample_format, metadata.duration_seconds, request_fingerprint)
