from __future__ import annotations

import hashlib
import math
import os
import wave
from array import array
from pathlib import Path

from game_visual_forge.contracts.music import MusicLoopEvidence, MusicProcessingOptions, MusicProcessingResult, MusicSourceRecord, music_hash


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _frames(handle, channels, chunk=4096):
    while True:
        raw = handle.readframes(chunk)
        if not raw:
            return
        values = array("h"); values.frombytes(raw)
        if __import__("sys").byteorder != "little": values.byteswap()
        for start in range(0, len(values), channels):
            yield tuple(int(values[start + c]) for c in range(channels))


def _write_frames(path, channels, rate, frames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels); handle.setsampwidth(2); handle.setframerate(rate)
        values = array("h")
        for frame in frames:
            values.extend(max(-32768, min(32767, int(value))) for value in frame)
            if len(values) >= channels * 4096:
                if __import__("sys").byteorder != "little": values.byteswap()
                handle.writeframes(values.tobytes()); values = array("h")
        if values:
            if __import__("sys").byteorder != "little": values.byteswap()
            handle.writeframes(values.tobytes())


def ingest_music_source(repo_root: Path, source_path: Path, attempt, ffprobe: Path) -> MusicSourceRecord:
    root = Path(repo_root).resolve(); source = Path(source_path).resolve()
    try: relative = source.relative_to(root).as_posix()
    except ValueError as exc: raise ValueError("source path must be inside repo root") from exc
    with wave.open(str(source), "rb") as handle:
        channels, rate, width, frame_count = handle.getnchannels(), handle.getframerate(), handle.getsampwidth(), handle.getnframes()
    if width != 2 or channels not in {1, 2} or rate <= 0 or frame_count <= 0:
        raise ValueError("music source must be non-empty 16-bit mono or stereo WAV")
    return MusicSourceRecord(relative, _sha256(source), "pcm_s16le", rate, channels, frame_count / rate, str(getattr(attempt, "provider", "unknown")), str(getattr(attempt, "attempt_id", "unknown")), str(getattr(attempt, "candidate_id", "candidate")))


def _convert_frames(source, start, count, target_rate=44100, target_channels=2):
    source.setpos(start)
    iterator = iter(_frames(source, source.getnchannels()))
    src_channels, src_rate = source.getnchannels(), source.getframerate()
    current = next(iterator, (0,) * src_channels); source_index = 0
    total_out = round(count * target_rate / src_rate)
    for output_index in range(total_out):
        target_index = min(count - 1, int(output_index * src_rate / target_rate))
        while source_index < target_index:
            current = next(iterator); source_index += 1
        if src_channels == 1: yield (current[0], current[0])
        else: yield (current[0], current[1])


def _scan_peak(path):
    peak = 0
    with wave.open(str(path), "rb") as handle:
        for frame in _frames(handle, handle.getnchannels()):
            peak = max(peak, *(abs(v) for v in frame))
    return peak


def _limit_peak(path, target_dbfs=-1.0):
    peak = _scan_peak(path); target = round(32767 * 10 ** (target_dbfs / 20))
    if peak <= target or peak == 0: return 0.0
    gain = target / peak
    temporary = Path(path).with_suffix(".peak.wav")
    with wave.open(str(path), "rb") as source:
        channels, rate = source.getnchannels(), source.getframerate()
        _write_frames(temporary, channels, rate, (tuple(round(v * gain) for v in frame) for frame in _frames(source, channels)))
    os.replace(temporary, path)
    return 20 * math.log10(gain)


def process_music_candidate(repo_root: Path, source: MusicSourceRecord, options: MusicProcessingOptions, ffmpeg: Path, ffprobe: Path) -> MusicProcessingResult:
    del ffmpeg, ffprobe
    root = Path(repo_root).resolve(); input_path = root / source.path
    with wave.open(str(input_path), "rb") as handle:
        rate, channels, frames = handle.getframerate(), handle.getnchannels(), handle.getnframes()
        start_seconds, end_seconds = options.trim_start_seconds, options.trim_end_seconds
        if options.duration_policy == "trim":
            if end_seconds is None or end_seconds > frames / rate: raise ValueError("trim end exceeds source duration")
            start = round(start_seconds * rate); count = round((end_seconds - start_seconds) * rate)
        else: start, count = 0, frames
        if count <= 0: raise ValueError("selected duration must be positive")
        output_path = root / "outputs" / "music" / "staging" / (Path(source.path).stem + "-music.wav")
        _write_frames(output_path, 2, 44100, _convert_frames(handle, start, count))
    gain_db = _limit_peak(output_path)
    with wave.open(str(output_path), "rb") as output_handle:
        actual_frames = output_handle.getnframes()
    processing = {"source": source.sha256, "options": options.to_dict(), "output_rate": 44100, "output_channels": 2, "gain_db": gain_db}
    return MusicProcessingResult(source.sha256, output_path.relative_to(root).as_posix(), _sha256(output_path), music_hash(processing), 44100, 2, actual_frames / 44100, source.sample_rate, source.channels, gain_db, source_path=source.path)


def _blend(left, right, crossfade):
    if not crossfade: return list(left) + list(right)
    output = list(left[:-crossfade])
    for index in range(crossfade):
        a = math.cos(index / max(1, crossfade - 1) * math.pi / 2); b = math.sin(index / max(1, crossfade - 1) * math.pi / 2)
        output.append(tuple(round(x * a + y * b) for x, y in zip(left[-crossfade + index], right[index])))
    output.extend(right[crossfade:])
    return output


def build_music_loop_evidence(wav_path: Path, *, start_seconds: float, end_seconds: float, crossfade_ms: int, ffmpeg: Path) -> MusicLoopEvidence:
    del ffmpeg
    wav_path = Path(wav_path)
    with wave.open(str(wav_path), "rb") as handle:
        rate, channels, frame_count = handle.getframerate(), handle.getnchannels(), handle.getnframes()
        if not 0 <= start_seconds < end_seconds <= frame_count / rate: raise ValueError("loop range is outside source")
        start, end = round(start_seconds * rate), round(end_seconds * rate); length = end - start; crossfade = round(crossfade_ms * rate / 1000)
        if crossfade < 0 or (crossfade and not 0 < 2 * crossfade < length): raise ValueError("crossfade must satisfy 0 < 2K < N")
        handle.setpos(start); values = array("h"); values.frombytes(handle.readframes(length));
        if __import__("sys").byteorder != "little": values.byteswap()
    segment = [tuple(int(values[i + c]) for c in range(channels)) for i in range(0, len(values), channels)]
    rounds = _blend(_blend(segment, segment, crossfade), segment, crossfade)
    three_path = wav_path.with_name(wav_path.stem + ".loop-3x.wav"); preview_path = wav_path.with_name(wav_path.stem + ".loop-boundary.wav")
    _write_frames(three_path, channels, rate, rounds)
    window = min(rate, length // 2)
    _write_frames(preview_path, channels, rate, segment[-window:] + segment[:window])
    boundary_error = sum(abs(a - b) for a, b in zip(segment[-1], segment[0])) / max(1, channels * 32768)
    evidence_data = three_path.read_bytes() + preview_path.read_bytes()
    return MusicLoopEvidence(_sha256(wav_path), start_seconds, end_seconds, crossfade_ms, length - crossfade, boundary_error, str(preview_path), str(three_path), hashlib.sha256(evidence_data).hexdigest())
