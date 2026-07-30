from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from tests._bootstrap import ROOT, SRC


class SpriteCliTests(unittest.TestCase):
    def run_cli(self, root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "game_visual_forge", *arguments],
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(SRC)},
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

    def make_request(self, root: Path) -> Path:
        path = root / "request.json"
        path.write_text(json.dumps({
            "schema_version": 1,
            "asset_id": "hero-run",
            "prompt": "A side-view hero running in place.",
            "output_dir": "outputs/hero-run",
            "source_preference": "existing-file",
            "canvas_width": 8,
            "canvas_height": 8,
            "layout": "grid",
            "frame_count": 4,
            "directions": ["right"],
            "outputs": ["frames", "sheet", "gif"],
            "reference_paths": [],
            "style_constraints": [],
            "identity_constraints": [],
            "action_name": "run",
            "frame_width": 4,
            "frame_height": 4,
            "grid_rows": 2,
            "grid_columns": 2,
            "background_removal": "chroma",
            "chroma_color": "#ff00ff",
            "target_engine_notes": "test",
        }), encoding="utf-8")
        return path

    def make_source(self, root: Path) -> Path:
        path = root / "inputs" / "source.png"
        path.parent.mkdir()
        image = Image.new("RGBA", (8, 8), (255, 0, 255, 255))
        draw = ImageDraw.Draw(image)
        for row in range(2):
            for column in range(2):
                left, top = column * 4, row * 4
                draw.rectangle((left + 1, top + 1, left + 2, top + 2), fill=(20, 30, 40, 255))
        image.save(path)
        return path

    def test_help_exposes_sprite_commands(self) -> None:
        result = self.run_cli(Path("."), "sprite", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        for command in ("plan", "route", "ingest", "process", "validate"):
            self.assertIn(command, result.stdout)

    def test_existing_file_flow_is_offline_and_recoverable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request = self.make_request(root)
            source = self.make_source(root)
            capabilities = root / "capabilities.json"
            capabilities.write_text(json.dumps({"schema_version": 1, "supported": False, "operations": []}), encoding="utf-8")
            run_dir = root / "run"
            plan = self.run_cli(root, "sprite", "plan", "--request", str(request), "--out-dir", str(run_dir), "--now", "2026-07-30T00:00:00Z")
            self.assertEqual(plan.returncode, 0, plan.stderr)
            route = self.run_cli(root, "sprite", "route", "--request", str(run_dir / "sprite-request.json"), "--capabilities", str(capabilities), "--selection", "existing-file", "--out", str(run_dir / "source-decision.json"), "--state", str(run_dir / "job-state.json"), "--now", "2026-07-30T00:01:00Z")
            self.assertEqual(route.returncode, 0, route.stderr)
            raw = self.run_cli(root, "sprite", "ingest", "--request", str(run_dir / "sprite-request.json"), "--decision", str(run_dir / "source-decision.json"), "--image", str(source), "--repo-root", str(root), "--out", str(run_dir / "raw-image.json"), "--state", str(run_dir / "job-state.json"), "--now", "2026-07-30T00:02:00Z")
            self.assertEqual(raw.returncode, 0, raw.stderr)
            processed = self.run_cli(root, "sprite", "process", "--request", str(run_dir / "sprite-request.json"), "--raw-image", str(run_dir / "raw-image.json"), "--repo-root", str(root), "--out-dir", str(root / "outputs" / "hero-run"), "--state", str(run_dir / "job-state.json"), "--now", "2026-07-30T00:03:00Z")
            self.assertEqual(processed.returncode, 0, processed.stderr)
            process_payload = json.loads(processed.stdout)
            staging = Path(process_payload["staging_dir"])
            if not staging.is_absolute():
                staging = root / staging
            review = root / "visual-review.json"
            review.write_text(json.dumps({"schema_version": 1, "checks": {
                "character-identity-consistency": "passed",
                "action-and-direction-correctness": "passed",
                "equipment-continuity": "passed",
                "anatomy-and-silhouette": "passed",
                "unwanted-text-or-watermark": "passed",
                "semantic-duplicate-frames": "passed",
            }}), encoding="utf-8")
            first = self.run_cli(root, "sprite", "validate", "--request", str(run_dir / "sprite-request.json"), "--raw-image", str(run_dir / "raw-image.json"), "--processing-result", str(staging / "processing-result.json"), "--repo-root", str(root), "--staging-dir", str(staging), "--final-dir", str(root / "outputs" / "hero-run"), "--state", str(run_dir / "job-state.json"), "--now", "2026-07-30T00:04:00Z")
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(json.loads(first.stdout)["status"], "needs_attention")
            second = self.run_cli(root, "sprite", "validate", "--request", str(run_dir / "sprite-request.json"), "--raw-image", str(run_dir / "raw-image.json"), "--processing-result", str(staging / "processing-result.json"), "--repo-root", str(root), "--staging-dir", str(staging), "--final-dir", str(root / "outputs" / "hero-run"), "--visual-review", str(review), "--state", str(run_dir / "job-state.json"), "--now", "2026-07-30T00:05:00Z")
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(json.loads(second.stdout)["status"], "completed")
            self.assertTrue((root / "outputs" / "hero-run" / "asset-manifest.json").is_file())


if __name__ == "__main__":
    unittest.main()
