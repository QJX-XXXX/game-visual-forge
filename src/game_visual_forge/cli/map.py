from __future__ import annotations

from dataclasses import replace
from pathlib import Path, PurePosixPath
from typing import Any

from game_visual_forge.cli.planning import build_map_execution_plan
from game_visual_forge.contracts import (
    JobState,
    JobStatus,
    MapRequest,
    MapSourceDecision,
    MapSourceType,
    ProviderPreflight,
    QualityStatus,
    RawImageRecord,
    SourceType,
    load_json,
)
from game_visual_forge.contracts.serialization import dump_json
from game_visual_forge.jobs import fingerprint_request, load_job, save_job, transition_job
from game_visual_forge.processing.images import ingest_image
from game_visual_forge.processing.map import MapProcessingResult, process_map
from game_visual_forge.processing.sprite import publish_verified_outputs
from game_visual_forge.quality.map import apply_map_visual_review, build_map_asset_manifest, validate_map_outputs
from game_visual_forge.routing import MapSourceCapabilities, route_map


def _request(path: Path) -> tuple[MapRequest, str]:
    request = MapRequest.from_dict(load_json(path))
    return request, fingerprint_request(request.to_dict())


def run_map_plan(request_path: Path, out_dir: Path, now: str) -> dict[str, Any]:
    request, fingerprint = _request(request_path)
    out_dir = out_dir.resolve()
    dump_json(out_dir / "map-request.json", request.to_dict())
    dump_json(out_dir / "execution-plan.json", build_map_execution_plan(request).to_dict())
    save_job(out_dir / "job-state.json", JobState(1, f"job-{request.asset_id}", request.asset_id, JobStatus.PLANNED, now, now, fingerprint))
    return {"schema_version": 1, "status": "planned", "request_path": "map-request.json", "plan_path": "execution-plan.json", "state_path": "job-state.json"}


def run_map_route(
    request_path: Path,
    capabilities_path: Path,
    selection: str | None,
    preflight_path: Path | None,
    out_path: Path,
    state_path: Path,
    now: str,
) -> dict[str, Any]:
    request, fingerprint = _request(request_path)
    capabilities_payload = load_json(capabilities_path)
    capabilities = MapSourceCapabilities(bool(capabilities_payload["supported"]), tuple(capabilities_payload["operations"]))
    preflight = None if preflight_path is None else ProviderPreflight.from_dict(load_json(preflight_path))
    decision = route_map(request, capabilities, selected_source=None if selection is None else MapSourceType(selection), provider_preflight=preflight)
    dump_json(out_path, decision.to_dict())
    state = load_job(state_path)
    if state.request_fingerprint != fingerprint:
        raise ValueError("source decision does not match map request")
    if not decision.requires_user_selection:
        if decision.selected_provider is not None:
            state = replace(state, provider=decision.selected_provider.value)
            state = transition_job(state, JobStatus.AWAITING_CONFIRMATION, now=now)
        else:
            state = transition_job(state, JobStatus.READY, now=now)
        save_job(state_path, state)
    return {"schema_version": 1, "status": state.status.value, "decision_path": str(out_path.name), "source_type": None if decision.source_type is None else decision.source_type.value, "requires_user_selection": decision.requires_user_selection, "requires_paid_confirmation": decision.requires_paid_confirmation}


def run_map_ingest(
    request_path: Path,
    decision_path: Path,
    image_path: Path,
    repo_root: Path,
    out_path: Path,
    state_path: Path,
    now: str,
) -> dict[str, Any]:
    request, fingerprint = _request(request_path)
    decision = MapSourceDecision.from_dict(load_json(decision_path))
    if decision.request_fingerprint != fingerprint or decision.source_type is None:
        raise ValueError("source decision does not match map request or has no source")
    record = ingest_image(repo_root, image_path, SourceType.EXISTING_FILE, fingerprint, provider=decision.selected_provider)
    dump_json(out_path, record.to_dict())
    state = transition_job(load_job(state_path), JobStatus.RUNNING, now=now)
    save_job(state_path, state)
    return {"schema_version": 1, "status": state.status.value, "raw_image_path": str(out_path.name), "sha256": record.sha256}


def run_map_process(
    request_path: Path,
    raw_image_path: Path,
    repo_root: Path,
    out_dir: Path,
    state_path: Path,
    now: str,
) -> dict[str, Any]:
    request, fingerprint = _request(request_path)
    record = RawImageRecord.from_dict(load_json(raw_image_path))
    if record.request_fingerprint != fingerprint:
        raise ValueError("raw image fingerprint does not match map request")
    result = process_map(repo_root, request, record, repo_root / PurePosixPath(request.output_dir))
    staging = repo_root / PurePosixPath(result.staging_dir)
    result_path = staging / "processing-result.json"
    dump_json(result_path, result.to_dict())
    state = transition_job(load_job(state_path), JobStatus.VERIFYING, now=now)
    save_job(state_path, state)
    return {"schema_version": 1, "status": state.status.value, "processing_result_path": str(result_path), "staging_dir": result.staging_dir}


def run_map_validate(
    request_path: Path,
    raw_image_path: Path,
    processing_result_path: Path,
    repo_root: Path,
    staging_dir: Path,
    final_dir: Path,
    visual_review_path: Path | None,
    state_path: Path,
    now: str,
) -> dict[str, Any]:
    request, fingerprint = _request(request_path)
    record = RawImageRecord.from_dict(load_json(raw_image_path))
    result = MapProcessingResult.from_dict(load_json(processing_result_path))
    if record.request_fingerprint != fingerprint:
        raise ValueError("raw image fingerprint does not match map request")
    report = validate_map_outputs(staging_dir, request, record, result)
    if visual_review_path is not None:
        report = apply_map_visual_review(report, load_json(visual_review_path))
    manifest = build_map_asset_manifest(staging_dir, request, record, result, report)
    dump_json(staging_dir / "quality-report.json", report.to_dict())
    dump_json(staging_dir / "asset-manifest.json", manifest.to_dict())
    published = publish_verified_outputs(staging_dir, final_dir, report)
    state = load_job(state_path)
    if state.status is JobStatus.NEEDS_ATTENTION:
        state = transition_job(state, JobStatus.VERIFYING, now=now)
    target = JobStatus.FAILED if report.deterministic_status is QualityStatus.FAILED else JobStatus.COMPLETED if published else JobStatus.NEEDS_ATTENTION
    state = transition_job(state, target, now=now)
    save_job(state_path, state)
    return {"schema_version": 1, "status": state.status.value, "published": published, "quality_status": manifest.quality_status, "final_dir": str(final_dir) if published else None}
