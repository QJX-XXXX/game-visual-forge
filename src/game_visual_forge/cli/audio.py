from __future__ import annotations

from pathlib import Path
from typing import Any

from game_visual_forge.contracts import (
    AudioGenerationResult,
    AudioProcessingResult,
    AudioProviderPreflight,
    AudioQualityReport,
    AudioRequest,
    AudioReview,
    AudioSourceRecord,
    JobState,
    JobStatus,
    load_json,
)
from game_visual_forge.contracts.serialization import dump_json
from game_visual_forge.jobs import fingerprint_request, load_job, save_job, transition_job
from game_visual_forge.providers.audio import generate_audio_candidates, run_audio_provider_models, run_audio_provider_preflight
from game_visual_forge.processing.audio import process_audio_candidates
from game_visual_forge.processing.audio_probe import discover_audio_toolchain, ingest_audio
from game_visual_forge.quality.audio import assess_audio_outputs, build_audio_manifests, publish_audio_outputs, record_audio_review, validate_reviewed_audio_outputs
from game_visual_forge.routing.audio import route_audio


def _request(path: Path) -> tuple[AudioRequest, str]:
    request = AudioRequest.from_dict(load_json(path))
    return request, fingerprint_request(request.to_dict())


def run_audio_plan(request_path: Path, out_dir: Path, now: str) -> dict[str, Any]:
    from game_visual_forge.contracts.audio import AudioIntakeStatus, assess_audio_intake
    raw = load_json(request_path)
    assessment = assess_audio_intake(raw, raw.get("confirmed_sha256"))
    if assessment.status is not AudioIntakeStatus.PLANNED:
        return {"schema_version": 1, "status": assessment.status.value, "missing_groups": [item.value for item in assessment.missing_groups], "confirmation_summary": assessment.confirmation_summary, "confirmation_sha256": assessment.confirmation_sha256}
    request = assessment.request
    out_dir.mkdir(parents=True, exist_ok=True)
    fingerprint = fingerprint_request(request.to_dict())
    plan_path = out_dir / "execution-plan.json"
    state_path = out_dir / "job-state.json"
    dump_json(plan_path, {"schema_version": 1, "asset_id": request.asset_id, "request_fingerprint": fingerprint, "steps": ["route", "ingest", "generate", "process", "review", "validate"]})
    save_job(state_path, JobState(1, f"job-{request.asset_id}", request.asset_id, JobStatus.PLANNED, now, now, fingerprint))
    return {"schema_version": 1, "status": "planned", "plan_path": str(plan_path), "state_path": str(state_path)}


def run_audio_route(request_path: Path, preflight_path: Path | None, out_path: Path, state_path: Path, now: str) -> dict[str, Any]:
    request, _ = _request(request_path)
    preflight = AudioProviderPreflight.from_dict(load_json(preflight_path)) if preflight_path else None
    decision = route_audio(request, preflight)
    dump_json(out_path, decision.__dict__)
    state = load_job(state_path)
    state = transition_job(state, JobStatus.NEEDS_USER_ACTION if decision.requires_user_action else JobStatus.READY, now=now)
    save_job(state_path, state)
    return {"schema_version": 1, "status": state.status.value, "decision_path": str(out_path)}


def run_audio_ingest(request_path: Path, source_path: Path, repo_root: Path, out_path: Path, state_path: Path, now: str, ffprobe: Path | None = None) -> dict[str, Any]:
    request, fingerprint = _request(request_path)
    record = ingest_audio(repo_root, source_path, request, fingerprint, ffprobe=ffprobe)
    dump_json(out_path, record.to_dict())
    state = transition_job(load_job(state_path), JobStatus.RUNNING, now=now)
    save_job(state_path, state)
    return {"schema_version": 1, "status": state.status.value, "source_record_path": str(out_path)}


def run_audio_generate(request_path: Path, decision_path: Path | None, source_path: Path | None, executable: Path, repo_root: Path, out_dir: Path, state_path: Path, now: str) -> dict[str, Any]:
    request, _ = _request(request_path)
    source = AudioSourceRecord.from_dict(load_json(source_path)) if source_path else None
    output_dir = repo_root / request.output_dir
    current = load_job(state_path)
    if current.status is JobStatus.READY:
        current = transition_job(current, JobStatus.RUNNING, now=now)
        save_job(state_path, current)
    result = generate_audio_candidates(request, out_dir / "attempts", executable, output_dir, source, now)
    result_path = out_dir / "generation-result.json"
    dump_json(result_path, result.to_dict())
    current = load_job(state_path)
    state = current if current.status is JobStatus.VERIFYING else transition_job(current, JobStatus.VERIFYING, now=now)
    save_job(state_path, state)
    return {"schema_version": 1, "status": state.status.value, "generation_result_path": str(result_path), "candidate_count": len(result.candidates)}


def run_audio_process(request_path: Path, generation_path: Path, source_path: Path | None, repo_root: Path, out_dir: Path, state_path: Path, now: str, ffmpeg: Path | None = None, ffprobe: Path | None = None) -> dict[str, Any]:
    request, _ = _request(request_path)
    generation = AudioGenerationResult.from_dict(load_json(generation_path))
    source = AudioSourceRecord.from_dict(load_json(source_path)) if source_path else None
    toolchain = discover_audio_toolchain(explicit_ffmpeg=ffmpeg, explicit_ffprobe=ffprobe)
    result = process_audio_candidates(repo_root, request, generation, source, toolchain.ffmpeg, toolchain.ffprobe)
    result_path = out_dir / "processing-result.json"
    dump_json(result_path, result.to_dict())
    current = load_job(state_path)
    state = current if current.status is JobStatus.VERIFYING else transition_job(current, JobStatus.VERIFYING, now=now)
    save_job(state_path, state)
    return {"schema_version": 1, "status": state.status.value, "processing_result_path": str(result_path)}


def run_audio_record_review(request_path: Path, generation_path: Path, processing_path: Path, quality_path: Path, checks_path: Path, selected_candidate: str, repo_root: Path, out_path: Path, now: str) -> dict[str, Any]:
    request, _ = _request(request_path)
    generation = AudioGenerationResult.from_dict(load_json(generation_path))
    processing = AudioProcessingResult.from_dict(load_json(processing_path))
    source = None
    report = assess_audio_outputs(repo_root, request, source, generation, processing)
    dump_json(quality_path, report.to_dict())
    artifact = next(item for item in processing.artifacts if item.candidate_id == selected_candidate)
    checks = {str(key): bool(value) for key, value in load_json(checks_path).items()}
    review = record_audio_review(repo_root, request, generation, processing, quality_path, selected_candidate, {"wav": repo_root / artifact.wav_path, "waveform": repo_root / artifact.waveform_path, "spectrum": repo_root / artifact.spectrum_path}, checks, now)
    dump_json(out_path, review.to_dict())
    return {"schema_version": 1, "review_path": str(out_path), "approved": all(review.checks.values()) and report.status == "passed"}


def run_audio_validate(request_path: Path, generation_path: Path, processing_path: Path, review_path: Path, quality_path: Path, repo_root: Path, final_dir: Path, now: str) -> dict[str, Any]:
    request, _ = _request(request_path)
    generation = AudioGenerationResult.from_dict(load_json(generation_path))
    processing = AudioProcessingResult.from_dict(load_json(processing_path))
    review = AudioReview.from_dict(load_json(review_path))
    report = AudioQualityReport.from_dict(load_json(quality_path))
    validated = validate_reviewed_audio_outputs(repo_root, request, generation, processing, report, review)
    manifests = build_audio_manifests(repo_root, request, generation, processing, validated, review)
    artifact = next(item for item in processing.artifacts if item.candidate_id == review.selected_candidate_id)
    published = publish_audio_outputs(repo_root / processing.staging_dir, final_dir, [repo_root / artifact.wav_path], manifests)
    return {"schema_version": 1, "status": "completed" if published else "needs_attention", "quality_status": validated.status, "final_dir": str(final_dir)}


def run_audio_provider_models_command(executable: Path, payload_path: Path, out_path: Path) -> dict[str, Any]:
    result = run_audio_provider_models(executable, load_json(payload_path))
    dump_json(out_path, result)
    return {"schema_version": 1, "models_path": str(out_path)}


def run_audio_provider_preflight_command(executable: Path, payload_path: Path, out_path: Path) -> dict[str, Any]:
    result = run_audio_provider_preflight(executable, load_json(payload_path))
    dump_json(out_path, result.to_dict())
    return {"schema_version": 1, "preflight_path": str(out_path), "available": result.available}
