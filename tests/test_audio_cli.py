from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

from tests._bootstrap import ROOT  # noqa: F401


LAUNCHER = ROOT / "skills" / "forge-text-audio" / "scripts" / "run.py"


class AudioCliTests(unittest.TestCase):
    def test_audio_launcher_exposes_complete_command_surface(self) -> None:
        result = subprocess.run([sys.executable, str(LAUNCHER), "audio", "sfx", "--help"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        for command in ("plan", "route", "ingest", "generate", "process", "record-review", "validate"):
            self.assertIn(command, result.stdout)

    def test_provider_help_is_reachable(self) -> None:
        result = subprocess.run([sys.executable, str(LAUNCHER), "audio", "sfx", "provider", "--help"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("preflight", result.stdout)


if __name__ == "__main__":
    unittest.main()
