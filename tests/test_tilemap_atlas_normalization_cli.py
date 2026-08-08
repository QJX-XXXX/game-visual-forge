from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tests._bootstrap import ROOT  # noqa: F401
from tests.test_normalize_tile_atlas import make_request, native_decision
from game_visual_forge.contracts.serialization import dump_json


class TilemapAtlasNormalizationCliTests(unittest.TestCase):
    def test_launcher_normalizes_pages_and_returns_final_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            request = make_request()
            request_path = root / "request.json"
            decision_path = root / "decision.json"
            dump_json(request_path, request.to_dict())
            dump_json(decision_path, native_decision(request).to_dict())
            source = root / "generated.png"
            Image.new("RGBA", (1024, 1024), (30, 50, 70, 255)).save(source)

            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "skills/forge-2d-map/scripts/run.py"),
                    "map", "tile", "normalize-atlases",
                    "--request", str(request_path),
                    "--decision", str(decision_path),
                    "--atlas-page", f"page-01={source}",
                    "--atlas-page", f"page-02={source}",
                    "--atlas-page", f"page-03={source}",
                    "--repo-root", str(root),
                    "--out-dir", str(root / "normalized"),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "normalized")
            self.assertEqual(payload["normalized_page_ids"], ["page-01", "page-02", "page-03"])
            self.assertTrue((root / "normalized" / "atlas-normalization-report.json").is_file())
            self.assertTrue((root / "normalized" / "page-01.png").is_file())

    def test_non_native_requires_explicit_cli_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            request = make_request()
            request_path = root / "request.json"
            decision_path = root / "decision.json"
            dump_json(request_path, request.to_dict())
            decision = native_decision(request).to_dict()
            decision["source_type"] = "existing-file"
            decision_path.write_text(json.dumps(decision), encoding="utf-8")
            source = root / "generated.png"
            Image.new("RGBA", (1024, 1024), (30, 50, 70, 255)).save(source)

            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "skills/forge-2d-map/scripts/run.py"),
                    "map", "tile", "normalize-atlases",
                    "--request", str(request_path),
                    "--decision", str(decision_path),
                    "--atlas-page", f"page-01={source}",
                    "--atlas-page", f"page-02={source}",
                    "--atlas-page", f"page-03={source}",
                    "--repo-root", str(root),
                    "--out-dir", str(root / "normalized"),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("agent-native", result.stderr)


if __name__ == "__main__":
    unittest.main()
