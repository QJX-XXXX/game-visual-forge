from __future__ import annotations

import json
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests._bootstrap import ROOT, SRC
from game_visual_forge.contracts import ExecutionPlan
from game_visual_forge.contracts import AssetBrief
from game_visual_forge.jobs import fingerprint_request
from game_visual_forge.jobs import load_job
from game_visual_forge.cli.main import main


class CliDryRunTests(unittest.TestCase):
    def test_parse_errors_use_the_json_protocol_with_exit_code_two(self):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            self.assertEqual(main(["sprite", "process"]), 2)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(json.loads(errors.getvalue())["error"]["code"], "invalid_request")

    def test_cli_distinguishes_data_io_and_internal_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            brief = root / "brief.json"
            args = ["dry-run", "--brief", str(brief), "--out-dir", str(root / "run"),
                    "--now", "2026-07-30T00:00:00Z"]
            errors = io.StringIO()
            with contextlib.redirect_stderr(errors):
                self.assertEqual(main(args), 1)
            self.assertEqual(json.loads(errors.getvalue())["error"]["code"], "io_error")

            brief.write_text('{"schema_version": 1}', encoding="utf-8")
            errors = io.StringIO()
            with contextlib.redirect_stderr(errors):
                self.assertEqual(main(args), 1)
            self.assertEqual(json.loads(errors.getvalue())["error"]["code"], "invalid_request")

            for failure in (RuntimeError("private detail"), TypeError("private detail"), KeyError("private detail")):
                with self.subTest(failure=type(failure).__name__):
                    errors = io.StringIO()
                    with patch("game_visual_forge.cli.main.run_dry_run", side_effect=failure), contextlib.redirect_stderr(errors):
                        self.assertEqual(main(args), 1)
                    payload = json.loads(errors.getvalue())["error"]
                    self.assertEqual(payload["code"], "internal_error")
                    self.assertFalse(payload["recoverable"])
                    self.assertNotIn("private detail", errors.getvalue())

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
            plan = ExecutionPlan.from_dict(
                json.loads((output / "execution-plan.json").read_text(encoding="utf-8"))
            )
            state = load_job(output / "job-state.json")
            self.assertEqual(payload["status"], "planned")
            self.assertTrue(payload["dry_run"])
            self.assertEqual(payload["plan_path"], "execution-plan.json")
            self.assertEqual(payload["state_path"], "job-state.json")
            self.assertEqual(plan.schema_version, 1)
            self.assertEqual(plan.plan_id, "plan-hero-run")
            self.assertEqual(plan.asset_id, "hero-run")
            self.assertEqual(plan.source_preference, "auto")
            self.assertTrue(plan.dry_run)
            self.assertEqual(plan.steps[0].action, "check-agent-native")
            self.assertEqual(plan.steps[1].depends_on, ("step-01",))
            self.assertEqual(state.schema_version, 1)
            self.assertEqual(state.job_id, "job-hero-run")
            self.assertEqual(state.asset_id, "hero-run")
            self.assertEqual(state.status.value, "planned")
            self.assertEqual(state.created_at, "2026-07-30T00:00:00Z")
            self.assertEqual(state.updated_at, "2026-07-30T00:00:00Z")
            self.assertEqual(state.artifact_paths, ())
            self.assertEqual(
                state.request_fingerprint,
                fingerprint_request(
                    AssetBrief.from_dict(
                        json.loads(brief.read_text(encoding="utf-8"))
                    ).to_dict()
                ),
            )


if __name__ == "__main__":
    unittest.main()
