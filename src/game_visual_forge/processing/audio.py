from __future__ import annotations

import array
import hashlib
import math
import shutil
import subprocess
import sys
import wave
from pathlib import Path
from typing import Any

from game_visual_forge.contracts.audio import AudioGenerationMode, AudioProcessedArtifact, AudioProcessingResult, AudioRequest, AudioSourceRecord, AudioUsageProfile
from game_visual_forge.contracts.audio_provider import AudioGenerationResult
from game_visual_forge.jobs.fingerprints import fingerprint_request
from .audio_metrics import read_pcm16_metrics


def _ffmpeg_argv(ffmpeg: Path, arguments: list[str]) -> list[str]:
    return ([sys.executable, str(ffmpeg)] if ffmpeg.suffix.lower() == ".py" else [str(ffmpeg)]) + arguments


def _run_ffmpeg(ffmpeg: Path, arguments: list[str]) -> None:
    completed = subprocess.run(_ffmpeg_argv(ffmpeg, arguments), capture_output=True, text=True, encoding="utf-8", errors="strict", shell=False, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {completed.stderr[-1000:]}")


def _read_pcm(path: Path) -> tuple[int, int, list[tuple[int, ...]]]:
    with wave.open(str(path), "rb") as handle:
        channels = handle.getnchannels()
        rate = handle.getframerate()
        if handle.getsampwidth() != 2:
            raise ValueError("expected 16-bit PCM")
        raw = handle.readframes(handle.getnframes())
    values = array.array("h")
    values.frombytes(raw)
    if sys.byteorder != "little":
        values.byteswap()
    frames = [tuple(int(values[index + channel]) for channel in range(channels)) for index in range(0, len(values), channels)]
    return channels, rate, frames


def _write_pcm(path: Path, channels: int, rate: int, frames: list[tuple[int, ...]]) -> None:
    values = array.array("h")
    for frame in frames:
        values.extend(max(-32768, min(32767, int(value))) for value in frame)
    if sys.byteorder != "little":
        values.byteswap()
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(values.tobytes())


def _normalize_pcm16_peak(path: Path, target_dbfs: float = -1.0) -> bool:
    channels, rate, frames = _read_pcm(path)
    peak = max((abs(value) for frame in frames for value in frame), default=0)
    if peak == 0 or peak >= 32767:
        return False
    target = round(32767 * math.pow(10.0, target_dbfs / 20.0))
    gain = target / peak
    normalized = [tuple(round(value * gain) for value in frame) for frame in frames]
    _write_pcm(path, channels, rate, normalized)
    return True


def _frame_at(frames: list[tuple[int, ...]], index: int, channels: int) -> tuple[int, ...]:
    if not frames:
        return (0,) * channels
    return frames[min(max(index, 0), len(frames) - 1)]


def _splice_protected(source_path: Path, generated_path: Path, output_path: Path, request: AudioRequest, source: AudioSourceRecord) -> None:
    source_channels, source_rate, source_frames = _read_pcm(source_path)
    generated_channels, generated_rate, generated_frames = _read_pcm(generated_path)
    if source_rate != 44100 or generated_rate != 44100:
        raise ValueError("protected splicing requires 44.1 kHz PCM")
    channels = source_channels
    if generated_channels != channels:
        raise ValueError("protected splicing requires matching channel count")
    guard = round(request.join_guard_ms * 44.1)
    if request.mode is AudioGenerationMode.INPAINT:
        start = round(float(request.edit_start_seconds) * 44100)
        end = round(float(request.edit_end_seconds) * 44100)
        output: list[tuple[int, ...]] = []
        for index in range(len(source_frames)):
            if index < max(0, start - guard) or index >= min(len(source_frames), end + guard):
                output.append(source_frames[index])
            elif index < start:
                ratio = (index - (start - guard)) / max(1, guard)
                left = source_frames[index]
                right = _frame_at(generated_frames, index, channels)
                output.append(tuple(round(a * (1 - ratio) + b * ratio) for a, b in zip(left, right)))
            elif index >= end:
                ratio = (index - end) / max(1, guard)
                left = _frame_at(generated_frames, index, channels)
                right = source_frames[index]
                output.append(tuple(round(a * (1 - ratio) + b * ratio) for a, b in zip(left, right)))
            else:
                output.append(_frame_at(generated_frames, index, channels))
        _write_pcm(output_path, channels, source_rate, output)
        return
    if request.mode is AudioGenerationMode.CONTINUE:
        target_frames = round(request.duration_seconds * 44100)
        join_start = max(0, len(source_frames) - guard)
        output = []
        for index in range(target_frames):
            if index < join_start:
                output.append(source_frames[index])
            elif index < len(source_frames):
                ratio = (index - join_start) / max(1, guard)
                left = source_frames[index]
                right = _frame_at(generated_frames, index, channels)
                output.append(tuple(round(a * (1 - ratio) + b * ratio) for a, b in zip(left, right)))
            else:
                output.append(_frame_at(generated_frames, index, channels))
        _write_pcm(output_path, channels, source_rate, output)


def process_audio_candidates(
    repo_root: Path,
    request: AudioRequest,
    generation: AudioGenerationResult,
    source: AudioSourceRecord | None,
    ffmpeg: Path,
    ffprobe: Path,
) -> AudioProcessingResult:
    del ffprobe
    root = repo_root.resolve()
    output_root = root / request.output_dir
    staging = output_root / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    fingerprint = fingerprint_request(request.to_dict())
    artifacts: list[AudioProcessedArtifact] = []
    for candidate in generation.candidates:
        raw = output_root / candidate.raw_path
        processed = staging / f"{candidate.candidate_id}.wav"
        channels = 1 if request.spatial_mode.value == "3d" else 2
        _run_ffmpeg(ffmpeg, ["-y", "-i", str(raw), "-ar", "44100", "-ac", str(channels), "-c:a", "pcm_s16le", str(processed)])
        if request.mode is AudioGenerationMode.TEXT_TO_AUDIO and request.usage_profile is AudioUsageProfile.ONE_SHOT and not request.loop:
            _normalize_pcm16_peak(processed)
        if source is not None and request.mode in {AudioGenerationMode.INPAINT, AudioGenerationMode.CONTINUE}:
            protected = staging / f"{candidate.candidate_id}-protected.wav"
            _splice_protected(root / source.path, processed, protected, request, source)
            processed = protected
        metrics = read_pcm16_metrics(processed)
        target = request.duration_seconds if request.mode is not AudioGenerationMode.INPAINT else (source.duration_seconds if source else request.duration_seconds)
        if abs(metrics.duration_seconds - target) > 1 / 44100:
            raise ValueError(f"candidate duration is not exact: {metrics.duration_seconds} != {target}")
        waveform = staging / f"{candidate.candidate_id}-waveform.png"
        spectrum = staging / f"{candidate.candidate_id}-spectrum.png"
        _run_ffmpeg(ffmpeg, ["-y", "-i", str(processed), "-lavfi", "showwavespic=s=1200x240:colors=white", "-frames:v", "1", str(waveform)])
        _run_ffmpeg(ffmpeg, ["-y", "-i", str(processed), "-lavfi", "showspectrumpic=s=1200x480:legend=disabled:color=channel", "-frames:v", "1", str(spectrum)])
        artifacts.append(AudioProcessedArtifact(1, candidate.candidate_id, processed.relative_to(root).as_posix(), waveform.relative_to(root).as_posix(), spectrum.relative_to(root).as_posix(), fingerprint))
    return AudioProcessingResult(1, fingerprint, tuple(artifacts), staging.relative_to(root).as_posix())
