from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from game_visual_forge.cli.planning import build_execution_plan
from game_visual_forge.contracts import AssetBrief, JobState, JobStatus, load_json
from game_visual_forge.contracts.serialization import dump_json
from game_visual_forge.jobs import fingerprint_request, load_job, save_job


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="game-visual-forge")
    commands = parser.add_subparsers(dest="command", required=True)

    dry_run = commands.add_parser("dry-run")
    dry_run.add_argument("--brief", type=Path, required=True)
    dry_run.add_argument("--out-dir", type=Path, required=True)
    dry_run.add_argument("--now", required=True)

    show_state = commands.add_parser("show-state")
    show_state.add_argument("--state", type=Path, required=True)
    return parser


def run_dry_run(brief_path: Path, out_dir: Path, now: str) -> dict[str, Any]:
    brief = AssetBrief.from_dict(load_json(brief_path))
    plan = build_execution_plan(brief)
    fingerprint = fingerprint_request(brief.to_dict())
    state = JobState(
        schema_version=1,
        job_id=f"job-{brief.asset_id}",
        asset_id=brief.asset_id,
        status=JobStatus.PLANNED,
        created_at=now,
        updated_at=now,
        request_fingerprint=fingerprint,
    )
    dump_json(out_dir.resolve() / "execution-plan.json", plan.to_dict())
    save_job(out_dir.resolve() / "job-state.json", state)
    return {
        "schema_version": 1,
        "status": state.status.value,
        "dry_run": True,
        "plan_path": str((out_dir.resolve() / "execution-plan.json")),
        "state_path": str((out_dir.resolve() / "job-state.json")),
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "dry-run":
            payload = run_dry_run(args.brief, args.out_dir, args.now)
        else:
            payload = load_job(args.state).to_dict()
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
