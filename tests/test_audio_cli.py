from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests._bootstrap import ROOT  # noqa: F401

from game_visual_forge.cli.audio import run_audio_provider_configure
from game_visual_forge.cli.main import build_parser


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
        for command in ("configure", "show-config", "models", "preflight"):
            self.assertIn(command, result.stdout)

    def test_provider_configure_help_has_path_controls(self) -> None:
        result = subprocess.run([sys.executable, str(LAUNCHER), "audio", "sfx", "provider", "configure", "--help"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        for argument in ("--root", "--python-executable", "--replace"):
            self.assertIn(argument, result.stdout)

    def test_configure_handler_can_target_a_repository_from_any_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "stable audio"
            python = root / "runtime" / ".venv" / "Scripts" / "python.exe"
            python.parent.mkdir(parents=True)
            python.write_bytes(b"fake")
            repo = Path(directory) / "repo"
            with patch("game_visual_forge.providers.audio_runtime._python_can_import", return_value=True):
                result = run_audio_provider_configure(root, python, False, repo_root=repo)
            self.assertEqual(result["status"], "configured")
            self.assertTrue((repo / "game-visual-forge.local.json").is_file())

    def test_parser_accepts_provider_defaults_without_legacy_required_flags(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["audio", "sfx", "provider", "preflight"])
        self.assertIsNone(args.executable)
        self.assertIsNone(args.payload)
        self.assertIsNone(args.out)


if __name__ == "__main__":
    unittest.main()
