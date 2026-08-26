from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests._bootstrap import ROOT
from tests.test_comfy_h3 import workflow
from tests.test_video_contract import valid_request


LAUNCHER = ROOT / "skills" / "forge-video-to-sprite" / "scripts" / "run.py"


class VideoCliTests(unittest.TestCase):
    def test_video_sprite_help_exposes_all_local_commands(self) -> None:
        result = subprocess.run([sys.executable, str(LAUNCHER), "video", "sprite", "--help"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        for command in ("plan", "route", "ingest", "process", "inspect-h3", "record-review", "validate"):
            self.assertIn(command, result.stdout)

    def test_inspect_h3_writes_sanitized_report(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            workflow_path = root / "workflow.json"
            report_path = root / "report.json"
            workflow_path.write_text(json.dumps(workflow()), encoding="utf-8")
            result = subprocess.run([sys.executable, str(LAUNCHER), "video", "sprite", "inspect-h3", "--workflow", str(workflow_path), "--out", str(report_path)], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertTrue(payload["ok"])
            self.assertEqual(json.loads(result.stdout)["status"], "inspected")

    def test_video_provider_help_exposes_all_provider_commands(self) -> None:
        result = subprocess.run([sys.executable, str(LAUNCHER), "video", "provider", "--help"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        for command in ("models", "preflight", "estimate", "submit", "query", "download"):
            self.assertIn(command, result.stdout)

    def test_plan_writes_machine_readable_state(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            request = root / "request.json"
            request.write_text(json.dumps(valid_request()), encoding="utf-8")
            out = root / "run"
            result = subprocess.run([sys.executable, str(LAUNCHER), "video", "sprite", "plan", "--request", str(request), "--out-dir", str(out), "--now", "2026-08-09T00:00:00Z"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((out / "execution-plan.json").is_file())
            self.assertEqual(json.loads(result.stdout)["status"], "planned")


if __name__ == "__main__":
    unittest.main()
