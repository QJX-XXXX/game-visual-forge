from __future__ import annotations

from dataclasses import replace
from pathlib import Path, PurePosixPath
from typing import Any

from game_visual_forge.cli.planning import build_tilemap_execution_plan
from game_visual_forge.contracts import (
    TilemapApprovalGate,
    UserApprovalRecord,
    record_user_approval,
    validate_user_approval_files,
    JobRejectionRecord,
    JobState,
    JobStatus,
    MapSourceCapabilities,
    MapSourceDecision,
    MapSourceType,
    ProviderPreflight,
    QualityStatus,
    RawImageRecord,
    SourceType,
    TileMapRequest,
    TileMapSourceSet,
    TileAtlasSourceRecord,
    TileObjectSourceRecord,
    RejectedArtifact,
    parse_atlas_page_argument,
    parse_object_asset_argument,
    load_json,
)
from game_visual_forge.contracts.serialization import dump_json
from game_visual_forge.jobs import fingerprint_request, load_job, save_job, transition_job
from game_visual_forge.processing.images import ingest_image, sha256_file
from game_visual_forge.processing.sprite import publish_verified_outputs
from game_visual_forge.processing.tilemap import TileMapProcessingResult, process_tilemap
from game_visual_forge.quality.tilemap import apply_tilemap_visual_review, build_tilemap_asset_manifest, validate_tilemap_outputs
from game_visual_forge.routing import route_map


def run_tilemap_reject(
    state_path: Path,
    run_root: Path,
    out_path: Path,
    reason_code: str,
    reason: str,
    now: str,
) -> dict[str, Any]:
    """Permanently reject a run while retaining immutable artifact evidence."""
    state = load_job(state_path)
    if state.status is JobStatus.REJECTED:
        raise ValueError("tilemap run is already rejected")
    run_root = run_root.resolve()
    if not run_root.is_dir():
        raise ValueError("run_root must be an existing directory")
    out_path = out_path.resolve()
    artifacts: list[RejectedArtifact] = []
    for path in sorted(run_root.rglob("*")):
        if not path.is_file() or path.resolve() == out_path:
            continue
        relative = path.relative_to(run_root).as_posix()
        artifacts.append(RejectedArtifact(relative, sha256_file(path)))
    record = JobRejectionRecord(
        schema_version=1,
        job_id=state.job_id,
        asset_id=state.asset_id,
        request_fingerprint=state.request_fingerprint,
        rejected_at=now,
        reason_code=reason_code,
        reason=reason,
        artifacts=tuple(artifacts),
    )
    dump_json(out_path, record.to_dict())
    rejected = transition_job(state, JobStatus.REJECTED, now=now, error_code=reason_code)
    save_job(state_path, rejected)
    return {
        "schema_version": 1,
        "status": rejected.status.value,
        "rejection_path": str(out_path),
        "artifact_count": len(artifacts),
        "reason_code": reason_code,
    }


def run_tilemap_record_approval(
    gate: str,
    artifact_arguments: list[str],
    out_path: Path,
    now: str,
    repo_root: Path,
) -> dict[str, Any]:
    artifacts: list[tuple[str, Path]] = []
    for argument in artifact_arguments:
        role, separator, path = argument.partition("=")
        if not separator or not role or not path:
            raise ValueError("--artifact must use role=path syntax")
        artifacts.append((role, Path(path)))
    record = record_user_approval(TilemapApprovalGate(gate), tuple(artifacts), repo_root, now)
    dump_json(out_path, record.to_dict())
    return {"schema_version": 1, "status": record.status.value, "gate": record.gate.value, "approval_path": str(out_path)}


def _request(path: Path) -> tuple[TileMapRequest, str]:
    request = TileMapRequest.from_dict(load_json(path))
    return request, fingerprint_request(request.to_dict())


def run_tilemap_plan(request_path: Path, out_dir: Path, now: str) -> dict[str, Any]:
    request, fingerprint = _request(request_path)
    out_dir = out_dir.resolve()
    dump_json(out_dir / "tilemap-request.json", request.to_dict())
    dump_json(out_dir / "execution-plan.json", build_tilemap_execution_plan(request).to_dict())
    save_job(out_dir / "job-state.json", JobState(1, f"job-{request.asset_id}", request.asset_id, JobStatus.PLANNED, now, now, fingerprint))
    return {"schema_version": 1, "status": "planned", "request_path": "tilemap-request.json", "plan_path": "execution-plan.json", "state_path": "job-state.json"}


def run_tilemap_route(
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
        raise ValueError("source decision does not match tilemap request")
    if not decision.requires_user_selection:
        if decision.selected_provider is not None:
            state = replace(state, provider=decision.selected_provider.value)
            state = transition_job(state, JobStatus.AWAITING_CONFIRMATION, now=now)
        else:
            state = transition_job(state, JobStatus.READY, now=now)
        save_job(state_path, state)
    return {"schema_version": 1, "status": state.status.value, "decision_path": str(out_path.name), "source_type": None if decision.source_type is None else decision.source_type.value, "requires_user_selection": decision.requires_user_selection, "requires_paid_confirmation": decision.requires_paid_confirmation}


def run_tilemap_ingest(
    request_path: Path,
    decision_path: Path,
    image_path: Path | None,
    atlas_page_arguments: list[str],
    repo_root: Path,
    out_path: Path,
    state_path: Path,
    now: str,
    object_asset_arguments: list[str] | None = None,
    style_approval_path: Path | None = None,
) -> dict[str, Any]:
    request, fingerprint = _request(request_path)
    if request.approval_workflow.value == "two_gate":
        if style_approval_path is None:
            raise ValueError("two-gate tilemap ingest requires --style-approval")
        validate_user_approval_files(load_json(style_approval_path), TilemapApprovalGate.STYLE_SAMPLE, repo_root)
    elif style_approval_path is not None:
        raise ValueError("legacy tilemap ingest does not accept --style-approval")
    decision = MapSourceDecision.from_dict(load_json(decision_path))
    if decision.request_fingerprint != fingerprint or decision.source_type is None:
        raise ValueError("source decision does not match tilemap request or has no source")
    if (image_path is None) == (not atlas_page_arguments):
        raise ValueError("provide exactly one of --image or --atlas-page")
    if image_path is not None:
        if request.object_assets:
            raise ValueError("hybrid tilemap ingest requires atlas pages and --object-asset arguments")
        record = ingest_image(repo_root, image_path, SourceType.EXISTING_FILE, fingerprint, provider=decision.selected_provider)
        dump_json(out_path, record.to_dict())
        output_path = str(out_path.name)
    else:
        pages = []
        for argument in atlas_page_arguments:
            atlas_id, page_path = parse_atlas_page_argument(argument)
            pages.append(TileAtlasSourceRecord(atlas_id, ingest_image(repo_root, page_path, SourceType.EXISTING_FILE, fingerprint, provider=decision.selected_provider)))
        object_asset_arguments = object_asset_arguments or []
        objects = []
        for argument in object_asset_arguments:
            asset_id, object_path = parse_object_asset_argument(argument)
            objects.append(TileObjectSourceRecord(asset_id, ingest_image(repo_root, object_path, SourceType.EXISTING_FILE, fingerprint, provider=decision.selected_provider)))
        expected_object_ids = tuple(item.asset_id for item in request.object_assets)
        if tuple(item.asset_id for item in objects) != expected_object_ids:
            raise ValueError(f"object asset arguments must match request object assets: expected {expected_object_ids}")
        source_set = TileMapSourceSet(1, tuple(pages), tuple(objects))
        expected_ids = tuple(page.atlas_id for page in request.resolved_atlas_pages)
        if tuple(page.atlas_id for page in source_set.pages) != expected_ids:
            raise ValueError(f"atlas page arguments must match request pages: expected {expected_ids}")
        dump_json(out_path, source_set.to_dict())
        output_path = str(out_path.name)
    state = load_job(state_path)
    if style_approval_path is not None:
        approval_relative = style_approval_path.resolve().relative_to(repo_root.resolve()).as_posix()
        state = replace(state, artifact_paths=(*state.artifact_paths, approval_relative))
    state = transition_job(state, JobStatus.RUNNING, now=now)
    save_job(state_path, state)
    return {"schema_version": 1, "status": state.status.value, "raw_image_path": output_path, "sha256": None if image_path is None else record.sha256}


def run_tilemap_process(
    request_path: Path,
    raw_image_path: Path,
    repo_root: Path,
    out_dir: Path,
    state_path: Path,
    now: str,
) -> dict[str, Any]:
    request, fingerprint = _request(request_path)
    payload = load_json(raw_image_path)
    record = RawImageRecord.from_dict(payload) if "pages" not in payload else TileMapSourceSet.from_dict(payload)
    source_fingerprint = record.request_fingerprint if isinstance(record, RawImageRecord) else record.pages[0].image.request_fingerprint
    if source_fingerprint != fingerprint:
        raise ValueError("raw image fingerprint does not match tilemap request")
    result = process_tilemap(repo_root, request, record, repo_root / PurePosixPath(request.output_dir))
    staging = repo_root / PurePosixPath(result.staging_dir)
    result_path = staging / "processing-result.json"
    dump_json(result_path, result.to_dict())
    state = transition_job(load_job(state_path), JobStatus.VERIFYING, now=now)
    save_job(state_path, state)
    return {"schema_version": 1, "status": state.status.value, "processing_result_path": str(result_path), "staging_dir": result.staging_dir}


def run_tilemap_validate(
    request_path: Path,
    raw_image_path: Path,
    processing_result_path: Path,
    repo_root: Path,
    staging_dir: Path,
    final_dir: Path,
    visual_review_path: Path | None,
    state_path: Path,
    now: str,
    style_approval_path: Path | None = None,
    assembled_approval_path: Path | None = None,
) -> dict[str, Any]:
    request, fingerprint = _request(request_path)
    if (final_dir.resolve().parent / "rejection.json").is_file():
        raise ValueError("rejected tilemap runs cannot be validated or published")
    payload = load_json(raw_image_path)
    record = RawImageRecord.from_dict(payload) if "pages" not in payload else TileMapSourceSet.from_dict(payload)
    source_fingerprint = record.request_fingerprint if isinstance(record, RawImageRecord) else record.pages[0].image.request_fingerprint
    result = TileMapProcessingResult.from_dict(load_json(processing_result_path))
    if source_fingerprint != fingerprint:
        raise ValueError("raw image fingerprint does not match tilemap request")
    approvals = {}
    if request.approval_workflow.value == "two_gate":
        if visual_review_path is not None:
            raise ValueError("two-gate tilemap validation does not accept --visual-review")
        if style_approval_path is None or assembled_approval_path is None:
            raise ValueError("two-gate tilemap validation requires style and assembled approvals")
        approvals["style"] = validate_user_approval_files(load_json(style_approval_path), TilemapApprovalGate.STYLE_SAMPLE, repo_root)
        approvals["assembled"] = validate_user_approval_files(load_json(assembled_approval_path), TilemapApprovalGate.ASSEMBLED_MAP, repo_root)
        dump_json(staging_dir / "style-approval.json", approvals["style"].to_dict())
        dump_json(staging_dir / "assembled-map-approval.json", approvals["assembled"].to_dict())
    elif style_approval_path is not None or assembled_approval_path is not None:
        raise ValueError("legacy tilemap validation does not accept two-gate approvals")
    report = validate_tilemap_outputs(staging_dir, request, record, result)
    if visual_review_path is not None:
        report = apply_tilemap_visual_review(report, load_json(visual_review_path))
    elif approvals:
        report = replace(report, visual_status=QualityStatus.PASSED)
    report_path = staging_dir / "map-quality-report.json"
    dump_json(report_path, report.to_dict())
    unity_path = staging_dir / result.unity_manifest_path
    unity = load_json(unity_path)
    unity["quality_report"] = report_path.name
    unity["quality_report_sha256"] = sha256_file(report_path)
    if approvals:
        unity["style_approval"] = "style-approval.json"
        unity["style_approval_sha256"] = sha256_file(staging_dir / "style-approval.json")
        unity["assembled_approval"] = "assembled-map-approval.json"
        unity["assembled_approval_sha256"] = sha256_file(staging_dir / "assembled-map-approval.json")
    dump_json(unity_path, unity)
    manifest = build_tilemap_asset_manifest(staging_dir, request, record, result, report)
    dump_json(staging_dir / "asset-manifest.json", manifest.to_dict())
    published = publish_verified_outputs(staging_dir, final_dir, report)
    state = load_job(state_path)
    if state.status is JobStatus.NEEDS_ATTENTION:
        state = transition_job(state, JobStatus.VERIFYING, now=now)
    target = JobStatus.FAILED if report.deterministic_status is QualityStatus.FAILED else JobStatus.COMPLETED if published else JobStatus.NEEDS_ATTENTION
    state = transition_job(state, target, now=now)
    save_job(state_path, state)
    return {"schema_version": 1, "status": state.status.value, "published": published, "quality_status": manifest.quality_status, "final_dir": str(final_dir) if published else None}
