from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any

from game_visual_forge.cli.planning import build_execution_plan
from game_visual_forge.cli.map import (
    run_map_ingest,
    run_map_plan,
    run_map_process,
    run_map_route,
    run_map_validate,
)
from game_visual_forge.cli.tilemap import (
    run_tilemap_ingest,
    run_tilemap_record_approval,
    run_tilemap_plan,
    run_tilemap_preflight_assets,
    run_tilemap_record_asset_review,
    run_tilemap_process,
    run_tilemap_reject,
    run_tilemap_route,
    run_tilemap_validate,
)
from game_visual_forge.cli.sprite import (
    run_sprite_ingest,
    run_sprite_plan,
    run_sprite_process,
    run_sprite_route,
    run_sprite_validate,
)
from game_visual_forge.contracts import AssetBrief, JobState, JobStatus, load_json
from game_visual_forge.contracts import MapSourceType
from game_visual_forge.contracts.serialization import dump_json
from game_visual_forge.contracts.sprite import SourceType
from game_visual_forge.errors import ForgeError
from game_visual_forge.jobs import fingerprint_request, load_job, save_job
from game_visual_forge.routing import NativeAttemptOutcome


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="game-visual-forge")
    commands = parser.add_subparsers(dest="command", required=True)

    dry_run = commands.add_parser("dry-run")
    dry_run.add_argument("--brief", type=Path, required=True)
    dry_run.add_argument("--out-dir", type=Path, required=True)
    dry_run.add_argument("--now", required=True)

    map_parser = commands.add_parser("map")
    map_commands = map_parser.add_subparsers(dest="map_command", required=True)

    map_plan = map_commands.add_parser("plan")
    map_plan.add_argument("--request", type=Path, required=True)
    map_plan.add_argument("--out-dir", type=Path, required=True)
    map_plan.add_argument("--now", required=True)

    map_route = map_commands.add_parser("route")
    map_route.add_argument("--request", type=Path, required=True)
    map_route.add_argument("--capabilities", type=Path, required=True)
    map_route.add_argument("--selection", choices=[item.value for item in MapSourceType])
    map_route.add_argument("--preflight", type=Path)
    map_route.add_argument("--out", type=Path, required=True)
    map_route.add_argument("--state", type=Path, required=True)
    map_route.add_argument("--now", required=True)

    map_ingest = map_commands.add_parser("ingest")
    map_ingest.add_argument("--request", type=Path, required=True)
    map_ingest.add_argument("--decision", type=Path, required=True)
    map_ingest.add_argument("--image", type=Path, required=True)
    map_ingest.add_argument("--repo-root", type=Path, required=True)
    map_ingest.add_argument("--out", type=Path, required=True)
    map_ingest.add_argument("--state", type=Path, required=True)
    map_ingest.add_argument("--now", required=True)

    map_process = map_commands.add_parser("process")
    map_process.add_argument("--request", type=Path, required=True)
    map_process.add_argument("--raw-image", type=Path, required=True)
    map_process.add_argument("--repo-root", type=Path, required=True)
    map_process.add_argument("--out-dir", type=Path, required=True)
    map_process.add_argument("--state", type=Path, required=True)
    map_process.add_argument("--now", required=True)

    map_validate = map_commands.add_parser("validate")
    map_validate.add_argument("--request", type=Path, required=True)
    map_validate.add_argument("--raw-image", type=Path, required=True)
    map_validate.add_argument("--processing-result", type=Path, required=True)
    map_validate.add_argument("--repo-root", type=Path, required=True)
    map_validate.add_argument("--staging-dir", type=Path, required=True)
    map_validate.add_argument("--final-dir", type=Path, required=True)
    map_validate.add_argument("--visual-review", type=Path)
    map_validate.add_argument("--state", type=Path, required=True)
    map_validate.add_argument("--now", required=True)

    tilemap = map_commands.add_parser("tile")
    tilemap_commands = tilemap.add_subparsers(dest="tilemap_command", required=True)

    tilemap_plan = tilemap_commands.add_parser("plan")
    tilemap_plan.add_argument("--request", type=Path, required=True)
    tilemap_plan.add_argument("--out-dir", type=Path, required=True)
    tilemap_plan.add_argument("--now", required=True)

    tilemap_route = tilemap_commands.add_parser("route")
    tilemap_route.add_argument("--request", type=Path, required=True)
    tilemap_route.add_argument("--capabilities", type=Path, required=True)
    tilemap_route.add_argument("--selection", choices=[item.value for item in MapSourceType])
    tilemap_route.add_argument("--preflight", type=Path)
    tilemap_route.add_argument("--out", type=Path, required=True)
    tilemap_route.add_argument("--state", type=Path, required=True)
    tilemap_route.add_argument("--now", required=True)

    tilemap_ingest = tilemap_commands.add_parser("ingest")
    tilemap_ingest.add_argument("--request", type=Path, required=True)
    tilemap_ingest.add_argument("--decision", type=Path, required=True)
    tilemap_ingest.add_argument("--image", type=Path)
    tilemap_ingest.add_argument("--atlas-page", action="append", default=[])
    tilemap_ingest.add_argument("--object-asset", action="append", default=[])
    tilemap_ingest.add_argument("--style-approval", type=Path)
    tilemap_ingest.add_argument("--preassembly-review", type=Path)
    tilemap_ingest.add_argument("--critical-assets-report", type=Path)
    tilemap_ingest.add_argument("--repo-root", type=Path, required=True)
    tilemap_ingest.add_argument("--out", type=Path, required=True)
    tilemap_ingest.add_argument("--state", type=Path, required=True)
    tilemap_ingest.add_argument("--now", required=True)

    tilemap_process = tilemap_commands.add_parser("process")
    tilemap_process.add_argument("--request", type=Path, required=True)
    tilemap_process.add_argument("--raw-image", type=Path, required=True)
    tilemap_process.add_argument("--repo-root", type=Path, required=True)
    tilemap_process.add_argument("--out-dir", type=Path, required=True)
    tilemap_process.add_argument("--state", type=Path, required=True)
    tilemap_process.add_argument("--now", required=True)

    tilemap_validate = tilemap_commands.add_parser("validate")
    tilemap_validate.add_argument("--request", type=Path, required=True)
    tilemap_validate.add_argument("--raw-image", type=Path, required=True)
    tilemap_validate.add_argument("--processing-result", type=Path, required=True)
    tilemap_validate.add_argument("--repo-root", type=Path, required=True)
    tilemap_validate.add_argument("--staging-dir", type=Path, required=True)
    tilemap_validate.add_argument("--final-dir", type=Path, required=True)
    tilemap_validate.add_argument("--visual-review", type=Path)
    tilemap_validate.add_argument("--style-approval", type=Path)
    tilemap_validate.add_argument("--assembled-approval", type=Path)
    tilemap_validate.add_argument("--state", type=Path, required=True)
    tilemap_validate.add_argument("--now", required=True)

    tilemap_reject_parser = tilemap_commands.add_parser("reject")
    tilemap_reject_parser.add_argument("--state", type=Path, required=True)
    tilemap_reject_parser.add_argument("--run-root", type=Path, required=True)
    tilemap_reject_parser.add_argument("--out", type=Path, required=True)
    tilemap_reject_parser.add_argument("--reason-code", required=True)
    tilemap_reject_parser.add_argument("--reason", required=True)
    tilemap_reject_parser.add_argument("--now", required=True)

    tilemap_approval = tilemap_commands.add_parser("record-approval")
    tilemap_approval.add_argument("--gate", choices=["style-sample", "assembled-map"], required=True)
    tilemap_approval.add_argument("--artifact", action="append", default=[])
    tilemap_approval.add_argument("--out", type=Path, required=True)
    tilemap_approval.add_argument("--repo-root", type=Path, default=Path.cwd())
    tilemap_approval.add_argument("--now", required=True)

    tilemap_preflight = tilemap_commands.add_parser("preflight-assets")
    tilemap_preflight.add_argument("--request", type=Path, required=True)
    tilemap_preflight.add_argument("--architecture", type=Path, required=True)
    tilemap_preflight.add_argument("--atlas-page", action="append", default=[])
    tilemap_preflight.add_argument("--object-asset", action="append", default=[])
    tilemap_preflight.add_argument("--repo-root", type=Path, required=True)
    tilemap_preflight.add_argument("--out-dir", type=Path, required=True)

    tilemap_review = tilemap_commands.add_parser("record-asset-review")
    tilemap_review.add_argument("--report", type=Path, required=True)
    tilemap_review.add_argument("--decisions", type=Path, required=True)
    tilemap_review.add_argument("--out", type=Path, required=True)
    tilemap_review.add_argument("--now", required=True)

    show_state = commands.add_parser("show-state")
    show_state.add_argument("--state", type=Path, required=True)

    sprite = commands.add_parser("sprite")
    sprite_commands = sprite.add_subparsers(dest="sprite_command", required=True)

    plan = sprite_commands.add_parser("plan")
    plan.add_argument("--request", type=Path, required=True)
    plan.add_argument("--out-dir", type=Path, required=True)
    plan.add_argument("--now", required=True)

    route = sprite_commands.add_parser("route")
    route.add_argument("--request", type=Path, required=True)
    route.add_argument("--capabilities", type=Path, required=True)
    route.add_argument("--native-outcome", choices=[item.value for item in NativeAttemptOutcome], default=NativeAttemptOutcome.NOT_ATTEMPTED.value)
    route.add_argument("--selection", choices=[item.value for item in SourceType])
    route.add_argument("--preflight", type=Path)
    route.add_argument("--out", type=Path, required=True)
    route.add_argument("--state", type=Path, required=True)
    route.add_argument("--now", required=True)

    ingest = sprite_commands.add_parser("ingest")
    ingest.add_argument("--request", type=Path, required=True)
    ingest.add_argument("--decision", type=Path, required=True)
    ingest.add_argument("--image", type=Path, required=True)
    ingest.add_argument("--repo-root", type=Path, required=True)
    ingest.add_argument("--out", type=Path, required=True)
    ingest.add_argument("--state", type=Path, required=True)
    ingest.add_argument("--now", required=True)

    process = sprite_commands.add_parser("process")
    process.add_argument("--request", type=Path, required=True)
    process.add_argument("--raw-image", type=Path, required=True)
    process.add_argument("--repo-root", type=Path, required=True)
    process.add_argument("--out-dir", type=Path, required=True)
    process.add_argument("--state", type=Path, required=True)
    process.add_argument("--now", required=True)

    validate = sprite_commands.add_parser("validate")
    validate.add_argument("--request", type=Path, required=True)
    validate.add_argument("--raw-image", type=Path, required=True)
    validate.add_argument("--processing-result", type=Path, required=True)
    validate.add_argument("--repo-root", type=Path, required=True)
    validate.add_argument("--staging-dir", type=Path, required=True)
    validate.add_argument("--final-dir", type=Path, required=True)
    validate.add_argument("--visual-review", type=Path)
    validate.add_argument("--state", type=Path, required=True)
    validate.add_argument("--now", required=True)
    return parser


def _relative_posix_path(path: Path, *, root: Path) -> str:
    return PurePosixPath(path.resolve().relative_to(root.resolve()).as_posix()).as_posix()


def run_dry_run(brief_path: Path, out_dir: Path, now: str) -> dict[str, Any]:
    brief = AssetBrief.from_dict(load_json(brief_path))
    plan = build_execution_plan(brief)
    fingerprint = fingerprint_request(brief.to_dict())
    out_dir = out_dir.resolve()
    plan_path = out_dir / "execution-plan.json"
    state_path = out_dir / "job-state.json"
    state = JobState(
        schema_version=1,
        job_id=f"job-{brief.asset_id}",
        asset_id=brief.asset_id,
        status=JobStatus.PLANNED,
        created_at=now,
        updated_at=now,
        request_fingerprint=fingerprint,
    )
    dump_json(plan_path, plan.to_dict())
    save_job(state_path, state)
    return {
        "schema_version": 1,
        "status": state.status.value,
        "dry_run": True,
        "plan_path": _relative_posix_path(plan_path, root=out_dir),
        "state_path": _relative_posix_path(state_path, root=out_dir),
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "dry-run":
            payload = run_dry_run(args.brief, args.out_dir, args.now)
        elif args.command == "show-state":
            payload = load_job(args.state).to_dict()
        elif args.command == "map" and args.map_command == "plan":
            payload = run_map_plan(args.request, args.out_dir, args.now)
        elif args.command == "map" and args.map_command == "route":
            payload = run_map_route(args.request, args.capabilities, args.selection, args.preflight, args.out, args.state, args.now)
        elif args.command == "map" and args.map_command == "ingest":
            payload = run_map_ingest(args.request, args.decision, args.image, args.repo_root, args.out, args.state, args.now)
        elif args.command == "map" and args.map_command == "process":
            payload = run_map_process(args.request, args.raw_image, args.repo_root, args.out_dir, args.state, args.now)
        elif args.command == "map" and args.map_command == "validate":
            payload = run_map_validate(args.request, args.raw_image, args.processing_result, args.repo_root, args.staging_dir, args.final_dir, args.visual_review, args.state, args.now)
        elif args.command == "map" and args.map_command == "tile" and args.tilemap_command == "plan":
            payload = run_tilemap_plan(args.request, args.out_dir, args.now)
        elif args.command == "map" and args.map_command == "tile" and args.tilemap_command == "route":
            payload = run_tilemap_route(args.request, args.capabilities, args.selection, args.preflight, args.out, args.state, args.now)
        elif args.command == "map" and args.map_command == "tile" and args.tilemap_command == "ingest":
            payload = run_tilemap_ingest(args.request, args.decision, args.image, args.atlas_page, args.repo_root, args.out, args.state, args.now, args.object_asset, args.style_approval, args.preassembly_review, args.critical_assets_report)
        elif args.command == "map" and args.map_command == "tile" and args.tilemap_command == "process":
            payload = run_tilemap_process(args.request, args.raw_image, args.repo_root, args.out_dir, args.state, args.now)
        elif args.command == "map" and args.map_command == "tile" and args.tilemap_command == "validate":
            payload = run_tilemap_validate(args.request, args.raw_image, args.processing_result, args.repo_root, args.staging_dir, args.final_dir, args.visual_review, args.state, args.now, args.style_approval, args.assembled_approval)
        elif args.command == "map" and args.map_command == "tile" and args.tilemap_command == "reject":
            payload = run_tilemap_reject(args.state, args.run_root, args.out, args.reason_code, args.reason, args.now)
        elif args.command == "map" and args.map_command == "tile" and args.tilemap_command == "record-approval":
            payload = run_tilemap_record_approval(args.gate, args.artifact, args.out, args.now, args.repo_root)
        elif args.command == "map" and args.map_command == "tile" and args.tilemap_command == "preflight-assets":
            payload = run_tilemap_preflight_assets(args.request, args.architecture, args.atlas_page, args.object_asset, args.repo_root, args.out_dir)
        elif args.command == "map" and args.map_command == "tile" and args.tilemap_command == "record-asset-review":
            payload = run_tilemap_record_asset_review(args.report, args.decisions, args.out, args.now)
        elif args.command == "sprite" and args.sprite_command == "plan":
            payload = run_sprite_plan(args.request, args.out_dir, args.now)
        elif args.command == "sprite" and args.sprite_command == "route":
            payload = run_sprite_route(args.request, args.capabilities, args.native_outcome, args.selection, args.preflight, args.out, args.state, args.now)
        elif args.command == "sprite" and args.sprite_command == "ingest":
            payload = run_sprite_ingest(args.request, args.decision, args.image, args.repo_root, args.out, args.state, args.now)
        elif args.command == "sprite" and args.sprite_command == "process":
            payload = run_sprite_process(args.request, args.raw_image, args.repo_root, args.out_dir, args.state, args.now)
        elif args.command == "sprite" and args.sprite_command == "validate":
            payload = run_sprite_validate(args.request, args.raw_image, args.processing_result, args.repo_root, args.staging_dir, args.final_dir, args.visual_review, args.state, args.now)
        else:
            raise ValueError("unsupported command")
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except ForgeError as error:
        print(json.dumps(error.to_dict(), ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 1
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        print(json.dumps({"schema_version": 1, "error": {"code": "invalid_request", "message": str(error), "recoverable": True, "context": {}}}, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 1
