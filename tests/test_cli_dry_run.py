from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests._bootstrap import ROOT, SRC


class CliDryRunTests(unittest.TestCase):
    def test_dry_run_writes_reloadable_plan_and_job(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            brief = root / "brief.json"
            output = root / "run"
            brief.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "asset_id": "hero-run",
                        "kind": "sprite",
                        "prompt": "A running hero.",
                        "output_dir": "outputs/hero-run",
                        "source_preference": "auto",
                        "reference_paths": [],
                        "canvas_width": 1024,
                        "canvas_height": 1024,
                        "frame_count": 8,
                    }
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "game_visual_forge",
                    "dry-run",
                    "--brief",
                    str(brief),
                    "--out-dir",
                    str(output),
                    "--now",
                    "2026-07-30T00:00:00Z",
                ],
                cwd=ROOT,
                env={**os.environ, "PYTHONPATH": str(SRC)},
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((output / "execution-plan.json").is_file())
            self.assertTrue((output / "job-state.json").is_file())
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "planned")
            self.assertTrue(payload["dry_run"])


if __name__ == "__main__":
    unittest.main()
