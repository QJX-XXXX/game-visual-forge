from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Sequence

from game_visual_forge.contracts.audio import AudioProcessingResult, AudioRequest, AudioSourceRecord
from game_visual_forge.contracts.audio_provider import AudioGenerationResult
from game_visual_forge.contracts.audio_quality import AudioQualityReport
from game_visual_forge.contracts.audio_review import AudioManifest, AudioReview, AudioSourcePlacement, UnityAudioManifest
from game_visual_forge.contracts.serialization import dump_json
from game_visual_forge.processing.audio_metrics import read_pcm16_metrics


UNITY_PROFILES: dict[str, dict[str, Any]] = {
    "ui": {"force_to_mono": True, "load_type": "DecompressOnLoad", "compression_format": "PCM", "preload_audio_data": True, "load_in_background": False},
    "one-shot": {"force_to_mono": None, "load_type": "DecompressOnLoad", "compression_format": "ADPCM", "preload_audio_data": True, "load_in_background": False},
    "scene": {"force_to_mono": True, "load_type": "DecompressOnLoad", "compression_format": "ADPCM", "preload_audio_data": True, "load_in_background": False},
    "looping-ambience": {"force_to_mono": None, "load_type": "Streaming", "compression_format": "Vorbis", "preload_audio_data": False, "load_in_background": True, "quality": 0.7},
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _report_sha256(report: AudioQualityReport) -> str:
    return hashlib.sha256(json.dumps(report.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def assess_audio_outputs(repo_root: Path, request: AudioRequest, source: AudioSourceRecord | None, generation: AudioGenerationResult, processing: AudioProcessingResult) -> AudioQualityReport:
    root = repo_root.resolve()
    failures: list[str] = []
    warnings: list[str] = []
    artifact_reports: dict[str, Any] = {}
    target = source.duration_seconds if request.mode.value == "inpaint" and source else request.duration_seconds
    for artifact in processing.artifacts:
        wav = root / artifact.wav_path
        waveform = root / artifact.waveform_path
        spectrum = root / artifact.spectrum_path
        if not wav.is_file() or wav.stat().st_size == 0:
            failures.append(f"{artifact.candidate_id}:empty-audio")
            continue
        if not waveform.is_file() or not spectrum.is_file():
            failures.append(f"{artifact.candidate_id}:missing-previews")
        try:
            metrics = read_pcm16_metrics(wav)
        except (OSError, ValueError) as error:
            failures.append(f"{artifact.candidate_id}:format-mismatch:{error}")
            continue
        if abs(metrics.duration_seconds - target) > 1 / 44100:
            failures.append(f"{artifact.candidate_id}:wrong-duration")
        if metrics.clipped_sample_count:
            failures.append(f"{artifact.candidate_id}:clipping")
        artifact_reports[artifact.candidate_id] = {
            "wav_sha256": _sha256(wav),
            "waveform_sha256": _sha256(waveform) if waveform.is_file() else None,
            "spectrum_sha256": _sha256(spectrum) if spectrum.is_file() else None,
            "sample_rate": metrics.sample_rate,
            "bit_depth": metrics.bit_depth,
            "channels": metrics.channels,
            "duration_seconds": metrics.duration_seconds,
            "peak_dbfs": metrics.peak_dbfs,
            "clipped_sample_count": metrics.clipped_sample_count,
            "dc_offset_abs": metrics.dc_offset_abs,
            "silent_sample_ratio": metrics.silent_sample_ratio,
            "loop_evidence": {"required": request.loop, "present": not request.loop},
            "protected_region_evidence": {"required": request.mode.value in {"inpaint", "continue"}, "present": request.mode.value not in {"inpaint", "continue"}},
        }
    if request.loop and not processing.artifacts:
        failures.append("missing-loop-evidence")
    if generation.candidates and not processing.artifacts:
        failures.append("no-processed-candidates")
    if source is not None:
        source_path = root / source.path
        if source_path.is_file() and _sha256(source_path) != source.sha256:
            failures.append("source-hash-mismatch")
    return AudioQualityReport(1, processing.request_fingerprint, "failed" if failures else "passed", tuple(failures), tuple(warnings), artifact_reports, source.sha256 if source else None)


def record_audio_review(repo_root: Path, request: AudioRequest, generation: AudioGenerationResult, processing: AudioProcessingResult, quality_report_path: Path, selected_candidate_id: str, artifact_paths: dict[str, Path], checks: dict[str, bool], reviewed_at: str) -> AudioReview:
    del request, generation
    if not quality_report_path.is_file():
        raise FileNotFoundError(quality_report_path)
    if not any(item.candidate_id == selected_candidate_id for item in processing.artifacts):
        raise ValueError("selected candidate is not a processed candidate")
    hashes = {key: _sha256(path) for key, path in artifact_paths.items()}
    return AudioReview.create(request_fingerprint=processing.request_fingerprint, selected_candidate_id=selected_candidate_id, quality_report_sha256=_sha256(quality_report_path), artifact_sha256=hashes, checks=checks, reviewed_at=reviewed_at)


def validate_reviewed_audio_outputs(repo_root: Path, request: AudioRequest, generation: AudioGenerationResult, processing: AudioProcessingResult, quality_report: AudioQualityReport, review: AudioReview) -> AudioQualityReport:
    del generation
    failures = list(quality_report.failures)
    if review.request_fingerprint != processing.request_fingerprint:
        failures.append("review-fingerprint-mismatch")
    if quality_report.status != "passed":
        failures.append("quality-report-failed")
    if not all(review.checks.values()):
        failures.append("manual-review-failed")
    selected = next((item for item in processing.artifacts if item.candidate_id == review.selected_candidate_id), None)
    if selected is None:
        failures.append("selected-candidate-missing")
    else:
        root = repo_root.resolve()
        current = {"wav": _sha256(root / selected.wav_path), "waveform": _sha256(root / selected.waveform_path), "spectrum": _sha256(root / selected.spectrum_path)}
        if current != review.artifact_sha256:
            failures.append("review-artifact-hash-mismatch")
    return AudioQualityReport(1, processing.request_fingerprint, "failed" if failures else "passed", tuple(dict.fromkeys(failures)), quality_report.warnings, quality_report.artifacts, quality_report.source_hash)


def build_audio_manifests(repo_root: Path, request: AudioRequest, generation: AudioGenerationResult, processing: AudioProcessingResult, quality_report: AudioQualityReport, review: AudioReview) -> tuple[AudioManifest, UnityAudioManifest, AudioSourcePlacement | None]:
    if quality_report.status != "passed" or not all(review.checks.values()):
        raise ValueError("cannot build manifests before approved quality and review")
    artifact = next((item for item in processing.artifacts if item.candidate_id == review.selected_candidate_id), None)
    if artifact is None:
        raise ValueError("selected candidate is missing")
    root = repo_root.resolve()
    files = {"wav": artifact.wav_path, "waveform": artifact.waveform_path, "spectrum": artifact.spectrum_path}
    hashes = {key: _sha256(root / path) for key, path in files.items()}
    manifest = AudioManifest(1, request.asset_id, processing.request_fingerprint, artifact.candidate_id, files, hashes)
    profile = dict(UNITY_PROFILES[request.usage_profile.value])
    if profile["force_to_mono"] is None:
        profile["force_to_mono"] = request.spatial_mode.value == "3d"
    unity = UnityAudioManifest(1, request.asset_id, artifact.wav_path, request.usage_profile.value, profile, hashes["wav"])
    placement = None
    if request.unity_scene_placement_requested:
        placement = AudioSourcePlacement(1, request.asset_id, request.audio_source_name or request.asset_id, artifact.wav_path, request.volume, request.play_on_awake, request.loop, request.spatial_mode.value, request.min_distance, request.max_distance)
    return manifest, unity, placement


def publish_audio_outputs(staging_dir: Path, final_dir: Path, selected_paths: Sequence[Path], manifests: Sequence[Any]) -> bool:
    final_dir.mkdir(parents=True, exist_ok=True)
    for path in selected_paths:
        shutil.copy2(path, final_dir / path.name)
    for manifest in manifests:
        if manifest is None:
            continue
        if isinstance(manifest, AudioManifest):
            name = "audio-manifest.json"
        elif isinstance(manifest, UnityAudioManifest):
            name = "unity-audio-manifest.json"
        else:
            name = "audio-source-placement.json"
        dump_json(final_dir / name, manifest.to_dict())
    return True
