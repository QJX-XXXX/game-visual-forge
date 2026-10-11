import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from tests._bootstrap import ROOT  # noqa: F401
from game_visual_forge.cli.main import main


class MusicCliTests(unittest.TestCase):
    def test_plan_and_route_are_offline(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); request = root / "request.json"; out_dir = root / "plan"
            request.write_text(json.dumps({"schema_version": 1, "asset_id": "menu-bgm", "brief": "soft piano", "usage": "bgm-linear", "target_duration_seconds": 30, "output_dir": "outputs/menu"}), encoding="utf-8")
            self.assertEqual(main(["audio", "music", "plan", "--request", str(request), "--out-dir", str(out_dir), "--now", "2026-10-10T00:00:00Z"]), 0)
            self.assertTrue((out_dir / "music-plan.json").exists())
            self.assertEqual(main(["audio", "music", "route", "--request", str(request), "--out", str(root / "route.json"), "--state", str(root / "state.json"), "--now", "2026-10-10T00:00:00Z"]), 0)

    def test_help_exposes_music_provider(self):
        result = subprocess.run([sys.executable, "skills/forge-game-music/scripts/run.py", "audio", "music", "provider", "--help"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("preflight", result.stdout)


if __name__ == "__main__": unittest.main()
