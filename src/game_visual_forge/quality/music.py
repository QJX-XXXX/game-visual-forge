from __future__ import annotations

import hashlib
import json
import shutil
import wave
from pathlib import Path

from game_visual_forge.contracts.music import MusicProcessingResult
from game_visual_forge.contracts.music_review import MusicQualityReport, MusicReview, REQUIRED_MUSIC_CHECKS
from game_visual_forge.contracts.serialization import dump_json


def _sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def _path(root, value):
    path = Path(value); return path if path.is_absolute() else Path(root) / path


def assess_music_outputs(request, source, processing: MusicProcessingResult, *, repo_root=None):
    root = Path(repo_root or "."); path = _path(root, processing.processed_path); failures = []; warnings = []
    if not path.is_file() or path.stat().st_size == 0: failures.append("empty-audio")
    metrics = {}
    try:
        with wave.open(str(path), "rb") as handle:
            rate, channels, width, frames = handle.getframerate(), handle.getnchannels(), handle.getsampwidth(), handle.getnframes()
            clipped = 0; peak = 0
            while True:
                raw = handle.readframes(4096)
                if not raw: break
                values = __import__("array").array("h"); values.frombytes(raw)
                peak = max(peak, *(abs(int(value)) for value in values))
                clipped += sum(1 for value in values if abs(int(value)) >= 32767)
            metrics = {"sample_rate": rate, "channels": channels, "bit_depth": width * 8, "duration_seconds": frames / rate if rate else 0, "peak_sample": peak, "clipped_sample_count": clipped}
            if (rate, channels, width) != (44100, 2, 2): failures.append("format-mismatch")
            if clipped: failures.append("clipping")
            if not frames: failures.append("non-finite-duration")
    except (OSError, wave.Error, ValueError): failures.append("unreadable-audio")
    if request.usage.value == "bgm-loop":
        if not processing.loop_evidence_path: failures.append("missing-loop-evidence")
        else:
            loop = _path(root, processing.loop_evidence_path)
            if not loop.is_file(): failures.append("missing-loop-evidence")
            elif processing.loop_evidence_sha256 and _sha(loop) != processing.loop_evidence_sha256: failures.append("loop-evidence-hash-mismatch")
    processed_hash = _sha(path) if path.is_file() else "0" * 64
    source_path = _path(root, source.path)
    if source_path.is_file() and _sha(source_path) != source.sha256: failures.append("source-hash-mismatch")
    status = "failed" if failures else "passed"
    return MusicQualityReport(1, hashlib.sha256(json.dumps(request.to_dict(), sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest(), processing.processing_fingerprint, status, tuple(failures), tuple(warnings), metrics, source.sha256, processed_hash, processing.loop_evidence_sha256)


def record_music_review(request, processing, quality, checks, now, repo_root=None):
    if set(checks) != REQUIRED_MUSIC_CHECKS: raise ValueError("review must contain exactly the six required music checks")
    root = Path(repo_root or "."); path = _path(root, processing.processed_path)
    artifacts = {"processed": _sha(path), "source": processing.source_sha256}
    if processing.loop_evidence_path:
        loop = _path(root, processing.loop_evidence_path); artifacts["loop_evidence"] = _sha(loop)
    return MusicReview.create(request_fingerprint=quality.request_fingerprint, processing_fingerprint=processing.processing_fingerprint, quality_report_sha256=quality.sha256, artifact_sha256=artifacts, checks=checks, reviewed_at=now)


def publish_music_bundle(repo_root, request, processing, quality, review, final_dir):
    if review is None: raise ValueError("listening review is required before publication")
    if quality.status != "passed" or not all(review.checks.values()): raise ValueError("quality and all listening checks must pass")
    review.assert_current(processing, quality, repo_root=repo_root)
    root = Path(repo_root); final = Path(final_dir); final.mkdir(parents=True, exist_ok=True)
    processed = _path(root, processing.processed_path); wav_name = request.asset_id + ".wav"; shutil.copy2(processed, final / wav_name)
    quality_dict = quality.to_dict(); review_dict = review.to_dict()
    dump_json(final / "music-quality.json", quality_dict); dump_json(final / "music-review.json", review_dict)
    manifest = {"schema_version": 1, "asset_id": request.asset_id, "profile": "music", "wav_path": wav_name, "sha256": _sha(final / wav_name)}
    dump_json(final / "music-manifest.json", manifest)
    result = {"wav": str(final / wav_name), "quality": quality_dict, "review": review_dict, "manifest": manifest}
    if request.unity_import_requested:
        unity = {"schema_version": 1, "asset_id": request.asset_id, "wav_path": wav_name, "profile": "music", "importer": {"load_type": "Streaming", "compression_format": "Vorbis", "preload_audio_data": False, "load_in_background": True, "quality": 0.7, "force_to_mono": False}, "sha256": manifest["sha256"]}
        dump_json(final / "unity-audio-manifest.json", unity); result["unity_manifest"] = unity
    return result
