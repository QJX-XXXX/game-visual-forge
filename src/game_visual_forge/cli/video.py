from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from game_visual_forge.contracts import JobState, JobStatus, VideoGenerationAttempt, VideoModelCatalogSnapshot, VideoSourceDecision, VideoSourceRecord, VideoSpriteRequest, VideoFrameRecord, VideoMotionReview
from game_visual_forge.contracts.serialization import dump_json, load_json
from game_visual_forge.contracts.video_provider import VideoProviderBackend
from game_visual_forge.jobs import fingerprint_request, load_job, save_job, transition_job
from game_visual_forge.processing.video_frames import build_sampling_plan, extract_highest_density
from game_visual_forge.processing.video_probe import discover_toolchain, ingest_video
from game_visual_forge.processing.video_sprite import process_video_sprite
from game_visual_forge.processing.video_review import calculate_temporal_metrics, create_anchor_diagnostic, create_contact_sheet, create_motion_difference, record_video_motion_review
from game_visual_forge.providers.cli import run_provider_command
from game_visual_forge.providers.video import download_video_attempt, query_video_attempt, submit_video_attempt
from game_visual_forge.quality.video import assess_video_outputs, build_video_asset_manifest, publish_video_outputs, validate_reviewed_video_outputs
from game_visual_forge.routing.video import route_video
from game_visual_forge.cli.planning import build_video_execution_plan


def _request(path: Path) -> tuple[VideoSpriteRequest, str]:
    request = VideoSpriteRequest.from_dict(load_json(path))
    return request, fingerprint_request(request.to_dict())


def run_video_plan(request_path: Path, out_dir: Path, now: str) -> dict[str, Any]:
    request, fingerprint = _request(request_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    plan_path = out_dir / "execution-plan.json"
    state_path = out_dir / "job-state.json"
    dump_json(plan_path, build_video_execution_plan(request).to_dict())
    save_job(state_path, JobState(1, f"job-{request.asset_id}", request.asset_id, JobStatus.PLANNED, now, now, fingerprint, provider=request.provider.value if request.provider else None))
    return {"schema_version": 1, "status": "planned", "plan_path": str(plan_path), "state_path": str(state_path)}


def run_video_route(request_path: Path, selection: str | None, backend: str | None, available_path: Path | None, out_path: Path, state_path: Path, now: str) -> dict[str, Any]:
    request, fingerprint = _request(request_path)
    available = None if available_path is None else load_json(available_path)
    decision = route_video(request, selected_provider=selection, selected_backend=backend, available_backends=None if available is None else available.get("backends", {}))
    dump_json(out_path, decision.to_dict())
    state = load_job(state_path)
    if not decision.requires_user_selection:
        state = transition_job(state, JobStatus.AWAITING_CONFIRMATION if decision.requires_paid_confirmation else JobStatus.READY, now=now)
        save_job(state_path, state)
    return {"schema_version": 1, "status": state.status.value, "decision_path": str(out_path)}


def run_video_provider_models(executable: Path, payload_path: Path, out_path: Path) -> dict[str, Any]:
    result = run_provider_command(executable, __import__("game_visual_forge.contracts", fromlist=["ProviderCommand"]).ProviderCommand.MODELS, load_json(payload_path))
    dump_json(out_path, result)
    return {"schema_version": 1, "snapshot_path": str(out_path)}


def run_video_provider_preflight(executable: Path, payload_path: Path, out_path: Path) -> dict[str, Any]:
    result = run_provider_command(executable, __import__("game_visual_forge.contracts", fromlist=["ProviderCommand"]).ProviderCommand.PREFLIGHT, load_json(payload_path))
    dump_json(out_path, result)
    return {"schema_version": 1, "preflight_path": str(out_path)}


def run_video_provider_estimate(executable: Path, payload_path: Path, out_path: Path) -> dict[str, Any]:
    result = run_provider_command(executable, __import__("game_visual_forge.contracts", fromlist=["ProviderCommand"]).ProviderCommand.ESTIMATE, load_json(payload_path))
    dump_json(out_path, result)
    return {"schema_version": 1, "estimate_path": str(out_path)}


def run_video_provider_submit(attempt_path: Path, confirmation_path: Path, executable: Path, now: str) -> dict[str, Any]:
    attempt = submit_video_attempt(attempt_path, confirmation_path, executable, now=now)
    return {"schema_version": 1, "status": attempt.status.value, "external_task_id": attempt.external_task_id}


def run_video_provider_query(attempt_path: Path, executable: Path, now: str) -> dict[str, Any]:
    attempt = query_video_attempt(attempt_path, executable, now=now)
    return {"schema_version": 1, "status": attempt.status.value, "external_task_id": attempt.external_task_id}


def run_video_provider_download(attempt_path: Path, executable: Path, output_dir: Path, now: str) -> dict[str, Any]:
    attempt = download_video_attempt(attempt_path, executable, output_dir, now=now)
    return {"schema_version": 1, "status": attempt.status.value, "downloaded_path": attempt.downloaded_path, "sha256": attempt.downloaded_sha256}


def run_video_ingest(request_path: Path, video_path: Path, repo_root: Path, out_path: Path, state_path: Path, now: str, ffprobe: Path | None = None) -> dict[str, Any]:
    request, fingerprint = _request(request_path)
    record = ingest_video(repo_root, video_path, fingerprint, ffprobe=ffprobe)
    dump_json(out_path, record.to_dict())
    state = transition_job(load_job(state_path), JobStatus.RUNNING, now=now)
    save_job(state_path, state)
    return {"schema_version": 1, "status": state.status.value, "source_record_path": str(out_path)}


def run_video_process(request_path: Path, source_path: Path, raw_frames_path: Path | None, repo_root: Path, out_dir: Path, state_path: Path, now: str, ffmpeg: Path | None = None) -> dict[str, Any]:
    request, fingerprint = _request(request_path)
    source = VideoSourceRecord.from_dict(load_json(source_path))
    if raw_frames_path is None or not raw_frames_path.is_file():
        toolchain = discover_toolchain(explicit_ffmpeg=ffmpeg)
        end = request.clip_end_seconds or source.duration_seconds
        sampling = build_sampling_plan(request.clip_start_seconds, end, request.frame_counts, loop=request.loop)
        relative_raw = out_dir.resolve().relative_to(repo_root.resolve()).as_posix() + "/raw-frames"
        extracted = extract_highest_density(repo_root, source, sampling.timestamps, toolchain.ffmpeg, output_dir=relative_raw)
        raw_frames_path = out_dir / "raw-frames.json"
        dump_json(raw_frames_path, {"schema_version": 1, "frames": [item.to_dict() for item in extracted]})
    raw_frames = tuple(VideoFrameRecord.from_dict(item) for item in load_json(raw_frames_path)["frames"])
    if source.request_fingerprint != fingerprint:
        raise ValueError("source record fingerprint does not match request")
    result = process_video_sprite(repo_root, request, source, raw_frames)
    result_path = repo_root / result.staging_dir / "processing-result.json"
    dump_json(result_path, result.to_dict())
    state = transition_job(load_job(state_path), JobStatus.VERIFYING, now=now)
    save_job(state_path, state)
    return {"schema_version": 1, "status": state.status.value, "processing_result_path": str(result_path)}


def run_video_assess(request_path: Path, source_path: Path, processing_path: Path, repo_root: Path, out_path: Path) -> dict[str, Any]:
    request, _ = _request(request_path)
    source = VideoSourceRecord.from_dict(load_json(source_path))
    processing = __import__("game_visual_forge.contracts", fromlist=["VideoProcessingResult"]).VideoProcessingResult.from_dict(load_json(processing_path))
    report = assess_video_outputs(repo_root, request, source, processing)
    dump_json(out_path, report.to_dict())
    return {"schema_version": 1, "quality_report_path": str(out_path), "deterministic_status": report.deterministic_status.value}


def run_video_record_review(request_path: Path, source_path: Path, processing_path: Path, repo_root: Path, quality_path: Path, out_path: Path, checks_path: Path, reviewed_at: str) -> dict[str, Any]:
    request, _ = _request(request_path)
    source = VideoSourceRecord.from_dict(load_json(source_path))
    processing = __import__("game_visual_forge.contracts", fromlist=["VideoProcessingResult"]).VideoProcessingResult.from_dict(load_json(processing_path))
    report = assess_video_outputs(repo_root, request, source, processing)
    dump_json(quality_path, report.to_dict())
    highest = max(request.frame_counts)
    frame_dir = repo_root / processing.artifacts[f"frames:{highest}"]
    from PIL import Image
    frames = []
    for path in sorted(frame_dir.glob("frame-*.png")):
        with Image.open(path) as image:
            frames.append(image.convert("RGBA"))
    timestamps = tuple(item.source_timestamp for item in processing.frame_records)
    evidence_dir = repo_root / processing.staging_dir / "delivery" / "previews"
    contact = create_contact_sheet(tuple(frames), timestamps or tuple(float(index) for index in range(len(frames))), evidence_dir / "contact-sheet.png")
    motion = create_motion_difference(tuple(frames), evidence_dir / "motion-difference.png")
    anchor = create_anchor_diagnostic(tuple(frames), evidence_dir / "anchor-diagnostic.png")
    preview = repo_root / processing.artifacts[f"gif:{highest}"]
    checks = {str(key): bool(value) for key, value in load_json(checks_path).items()}
    review = record_video_motion_review(repo_root, source.request_fingerprint, source.sha256, quality_path, {"contact-sheet": contact, "motion-difference": motion, "anchor-diagnostic": anchor, "preview": preview}, checks, all(checks.values()), reviewed_at)
    dump_json(out_path, review.to_dict())
    return {"schema_version": 1, "review_path": str(out_path), "approved": review.approved, "review_sha256": review.review_sha256}


def run_video_validate(request_path: Path, source_path: Path, processing_path: Path, review_path: Path, quality_path: Path, repo_root: Path, final_dir: Path, now: str) -> dict[str, Any]:
    request, _ = _request(request_path)
    source = VideoSourceRecord.from_dict(load_json(source_path))
    processing = __import__("game_visual_forge.contracts", fromlist=["VideoProcessingResult"]).VideoProcessingResult.from_dict(load_json(processing_path))
    review = __import__("game_visual_forge.contracts", fromlist=["VideoMotionReview"]).VideoMotionReview.from_dict(load_json(review_path))
    highest = max(request.frame_counts)
    report = validate_reviewed_video_outputs(repo_root, request, source, processing, review, quality_path, {"preview": repo_root / processing.artifacts[f"gif:{highest}"]})
    manifest = build_video_asset_manifest(repo_root, request, source, processing, report)
    published = publish_video_outputs(repo_root / processing.staging_dir, final_dir, report, manifest)
    return {"schema_version": 1, "status": "completed" if published else "needs_attention", "published": published, "quality_status": report.visual_status.value}
