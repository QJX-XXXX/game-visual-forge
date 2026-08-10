from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from PIL import Image

from tests._bootstrap import ROOT  # noqa: F401
from tests.test_normalize_tile_atlas import make_request
from tests.tilemap_workflow_fixtures import build_workflow_request_payload
from game_visual_forge.contracts import (
    GridRect,
    LayoutStrategy,
    SourcePreference,
    TileMapApprovalWorkflow,
    TileMapIntake,
    TileMapRequest,
    TileSetProfile,
)
from game_visual_forge.contracts.serialization import dump_json, load_json
from game_visual_forge.contracts.tilemap_intake import tilemap_confirmation_sha256


class TilemapNormalizationCleanWorkflowTests(unittest.TestCase):
    def test_cli_workflow_publishes_normalization_evidence(self) -> None:
        output_root = ROOT / "outputs"
        output_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=output_root) as temp:
            run = Path(temp)
            source_dir = run / "source"
            generated_dir = run / "generated"
            source_dir.mkdir()
            generated_dir.mkdir()
            base = make_request()
            intake = TileMapIntake.from_dict(build_workflow_request_payload()["intake"])
            intake = replace(intake, layout_strategy=LayoutStrategy.REUSABLE, continuity_features=("terrain",), requirements_confirmed=False, confirmed_summary_sha256=None)
            intake = replace(intake, requirements_confirmed=True, confirmed_summary_sha256=tilemap_confirmation_sha256(intake))
            request = TileMapRequest(**{
                **base.__dict__,
                "source_preference": SourcePreference.AGENT_NATIVE,
                "tileset_profile": TileSetProfile.DEMAND_DRIVEN,
                "approval_workflow": TileMapApprovalWorkflow.TWO_GATE,
                "gameplay_crop": GridRect(0, 0, 2, 2),
                "intake": intake,
            })
            request_path = source_dir / "tilemap-request.json"
            dump_json(request_path, request.to_dict())
            dump_json(source_dir / "capabilities.json", {"supported": True, "operations": ["text-to-image"]})
            for index in range(1, 4):
                Image.new("RGBA", (1024, 1024), (20 * index, 50, 90, 255)).save(generated_dir / f"page-{index:02d}-generated.png")

            launcher = ROOT / "skills" / "forge-2d-map" / "scripts" / "run.py"

            def run_cli(*args: str) -> dict:
                result = subprocess.run(
                    [sys.executable, str(launcher), *args],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    check=False,
                )
                if result.returncode != 0:
                    self.fail(f"CLI failed: {args}\nstdout={result.stdout}\nstderr={result.stderr}")
                return json.loads(result.stdout)

            job = run / "job"
            run_cli("map", "tile", "plan", "--request", str(request_path), "--out-dir", str(job), "--now", "2026-08-09T12:00:00Z")
            run_cli("map", "tile", "route", "--request", str(job / "tilemap-request.json"), "--capabilities", str(source_dir / "capabilities.json"), "--selection", "agent-native", "--out", str(job / "source-decision.json"), "--state", str(job / "job-state.json"), "--now", "2026-08-09T12:01:00Z")
            normalized = run / "normalized"
            run_cli("map", "tile", "normalize-atlases", "--request", str(job / "tilemap-request.json"), "--decision", str(job / "source-decision.json"), "--atlas-page", f"page-01={generated_dir / 'page-01-generated.png'}", "--atlas-page", f"page-02={generated_dir / 'page-02-generated.png'}", "--atlas-page", f"page-03={generated_dir / 'page-03-generated.png'}", "--repo-root", str(ROOT), "--out-dir", str(normalized))
            preflight = run / "preflight"
            run_cli("map", "tile", "preflight-assets", "--request", str(job / "tilemap-request.json"), "--architecture", str(job / "architecture-decision.json"), "--decision", str(job / "source-decision.json"), "--normalization-report", str(normalized / "atlas-normalization-report.json"), "--atlas-page", f"page-01={normalized / 'page-01.png'}", "--atlas-page", f"page-02={normalized / 'page-02.png'}", "--atlas-page", f"page-03={normalized / 'page-03.png'}", "--repo-root", str(ROOT), "--out-dir", str(preflight))
            preflight_report = load_json(preflight / "critical-assets-report.json")
            dump_json(preflight / "decisions.json", {"schema_version": 1, "assets": [{"asset_id": item["asset_id"], "status": "accepted", "reason_code": "pass", "reason": "synthetic clean workflow"} for item in preflight_report["candidates"]]})
            run_cli("map", "tile", "record-asset-review", "--report", str(preflight / "critical-assets-report.json"), "--decisions", str(preflight / "decisions.json"), "--out", str(preflight / "preassembly-review.json"), "--now", "2026-08-09T12:02:00Z")

            style_sample = source_dir / "style-sample.png"
            Image.new("RGBA", (64, 64), (90, 160, 100, 255)).save(style_sample)
            art_direction = source_dir / "art-direction.json"
            dump_json(art_direction, {"style": "synthetic"})
            run_cli("map", "tile", "record-approval", "--gate", "style-sample", "--artifact", f"style-sample={style_sample}", "--artifact", f"art-direction={art_direction}", "--out", str(source_dir / "style-approval.json"), "--repo-root", str(ROOT), "--now", "2026-08-09T12:03:00Z")

            raw_source = run / "raw" / "source-set.json"
            raw_source.parent.mkdir()
            run_cli("map", "tile", "ingest", "--request", str(job / "tilemap-request.json"), "--decision", str(job / "source-decision.json"), "--atlas-page", f"page-01={normalized / 'page-01.png'}", "--atlas-page", f"page-02={normalized / 'page-02.png'}", "--atlas-page", f"page-03={normalized / 'page-03.png'}", "--repo-root", str(ROOT), "--out", str(raw_source), "--state", str(job / "job-state.json"), "--style-approval", str(source_dir / "style-approval.json"), "--preassembly-review", str(preflight / "preassembly-review.json"), "--critical-assets-report", str(preflight / "critical-assets-report.json"), "--now", "2026-08-09T12:04:00Z")
            processed = run_cli("map", "tile", "process", "--request", str(job / "tilemap-request.json"), "--raw-image", str(raw_source), "--repo-root", str(ROOT), "--out-dir", str(run / "processed"), "--state", str(job / "job-state.json"), "--now", "2026-08-09T12:05:00Z")
            staging = ROOT / processed["staging_dir"]
            approval_args = []
            for role in ("review-sheet", "tilemap-preview", "gameplay-crop", "tilemap-placement", "tilemap-objects", "tilemap-collision", "asset-set"):
                approval_args.extend(["--artifact", f"{role}={staging / 'tilemap-preview.png'}"])
            run_cli("map", "tile", "record-approval", "--gate", "assembled-map", *approval_args, "--out", str(source_dir / "assembled-map-approval.json"), "--repo-root", str(ROOT), "--now", "2026-08-09T12:06:00Z")
            final_dir = run / "final"
            validated = run_cli("map", "tile", "validate", "--request", str(job / "tilemap-request.json"), "--raw-image", str(raw_source), "--processing-result", str(staging / "processing-result.json"), "--repo-root", str(ROOT), "--staging-dir", str(staging), "--final-dir", str(final_dir), "--state", str(job / "job-state.json"), "--style-approval", str(source_dir / "style-approval.json"), "--assembled-approval", str(source_dir / "assembled-map-approval.json"), "--now", "2026-08-09T12:07:00Z")

            manifest = load_json(final_dir / "asset-manifest.json")
            self.assertTrue(validated["published"])
            self.assertTrue(any(item["role"] == "atlas-normalization-report" for item in manifest["artifacts"]))
            self.assertTrue((final_dir / "tileset-page-01.png").is_file())


if __name__ == "__main__":
    unittest.main()
