from __future__ import annotations

import array
import math
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class PcmMetrics:
    sample_rate: int
    bit_depth: int
    channels: int
    frame_count: int
    duration_seconds: float
    peak_sample: int
    peak_dbfs: float
    rms_dbfs: float
    crest_db: float
    transient_to_tail_db: float
    clipped_sample_count: int
    dc_offset_abs: float
    silent_sample_ratio: float
    rms_signature: tuple[float, ...]


def _read_samples(path: Path) -> tuple[int, int, bytes, array.array]:
    with wave.open(str(path), "rb") as handle:
        channels = handle.getnchannels()
        sample_rate = handle.getframerate()
        width = handle.getsampwidth()
        frames = handle.getnframes()
        data = handle.readframes(frames)
    if width != 2 or sample_rate != 44100:
        raise ValueError("audio must be 44.1 kHz 16-bit PCM")
    samples = array.array("h")
    samples.frombytes(data)
    if __import__("sys").byteorder != "little":
        samples.byteswap()
    return channels, sample_rate, data, samples


def read_pcm16_metrics(path: Path) -> PcmMetrics:
    channels, sample_rate, _data, samples = _read_samples(path)
    if channels not in {1, 2}:
        raise ValueError("audio must have one or two channels")
    frame_count = len(samples) // channels
    peak = max((abs(int(value)) for value in samples), default=0)
    clipped = sum(1 for value in samples if abs(int(value)) >= 32767)
    mean = sum(int(value) for value in samples) / max(1, len(samples))
    silent = sum(1 for value in samples if abs(int(value)) <= 16)
    block = max(1, len(samples) // 32)
    signature = []
    for start in range(0, len(samples), block):
        values = samples[start : start + block]
        signature.append(math.sqrt(sum(float(value) * float(value) for value in values) / max(1, len(values))) / 32768.0)
    peak_dbfs = -math.inf if peak == 0 else 20.0 * math.log10(peak / 32767.0)
    rms = math.sqrt(sum(float(value) * float(value) for value in samples) / max(1, len(samples))) / 32768.0
    rms_dbfs = -math.inf if rms == 0 else 20.0 * math.log10(rms)
    crest_db = math.inf if rms == 0 else peak_dbfs - rms_dbfs
    tail_blocks = signature[-max(1, len(signature) // 4) :]
    tail_rms = math.sqrt(sum(value * value for value in tail_blocks) / max(1, len(tail_blocks)))
    transient_rms = max(signature, default=0.0)
    if tail_rms == 0:
        transient_to_tail_db = math.inf if transient_rms > 0 else 0.0
    else:
        transient_to_tail_db = 20.0 * math.log10(max(transient_rms, 1e-20) / tail_rms)
    return PcmMetrics(sample_rate, 16, channels, frame_count, frame_count / sample_rate, peak, peak_dbfs, rms_dbfs, crest_db, transient_to_tail_db, clipped, abs(mean) / 32768.0, silent / max(1, len(samples)), tuple(signature))


def compare_protected_samples(expected: Path, actual: Path, protected_ranges: Sequence[tuple[int, int]]) -> bool:
    with wave.open(str(expected), "rb") as left, wave.open(str(actual), "rb") as right:
        if (left.getnchannels(), left.getframerate(), left.getsampwidth()) != (right.getnchannels(), right.getframerate(), right.getsampwidth()):
            return False
        channels = left.getnchannels()
        left_data = left.readframes(left.getnframes())
        right_data = right.readframes(right.getnframes())
    frame_width = channels * 2
    for start, end in protected_ranges:
        if start < 0 or end < start:
            return False
        if left_data[start * frame_width : end * frame_width] != right_data[start * frame_width : end * frame_width]:
            return False
    return True
