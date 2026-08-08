from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import json

from PIL import Image, ImageDraw

from tests._bootstrap import ROOT  # noqa: F401
from tests.tilemap_workflow_fixtures import build_workflow_request_payload
from game_visual_forge.contracts import PreassemblyAssetDecision, PreassemblyReviewStatus, TileMapRequest, QualityStatus, record_preassembly_review, validate_preassembly_review
from game_visual_forge.jobs import fingerprint_request
from game_visual_forge.processing.tilemap_asset_preflight import preflight_tilemap_assets
from game_visual_forge.routing import select_tilemap_architecture


class TilemapAssetPreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.request = TileMapRequest.from_dict(build_workflow_request_payload())
        self.architecture = select_tilemap_architecture(self.request, fingerprint_request(self.request.to_dict()))
        (self.root / "source").mkdir()
        (self.root / "source" / "foundation.prompt.txt").write_text("coherent foundation", encoding="utf-8")
        self.foundation = self.root / "foundation.png"
        Image.new("RGBA", self.request.expected_atlas_size, (60, 170, 80, 255)).save(self.foundation)
        self.bridge = self.root / "bridge-east-west-bridge.png"
        Image.new("RGBA", (96, 48), (150, 100, 60, 255)).save(self.bridge)
        self.object = self.root / "inn.png"
        image = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
        ImageDraw.Draw(image).rectangle((20, 20, 75, 75), fill=(180, 120, 60, 255))
        image.save(self.object)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def candidates(self):
        return (("foundation", "foundation", self.foundation), ("bridge-east-west-bridge", "bridge", self.bridge), ("inn", "object", self.object))

    def test_preflight_writes_report_sheet_and_bridge_focus(self) -> None:
        out = self.root / "preflight"
        report = preflight_tilemap_assets(self.root, self.request, self.architecture, self.candidates(), out)
        self.assertTrue((out / "critical-assets-report.json").is_file())
        self.assertTrue((out / "critical-assets-review-sheet.png").is_file())
        self.assertTrue((out / "focus" / "bridge-east-west-bridge.png").is_file())
        self.assertEqual(report.deterministic_status, QualityStatus.PASSED)

    def test_object_with_opaque_rectangular_background_fails(self) -> None:
        Image.new("RGBA", (96, 96), (180, 120, 60, 255)).save(self.object)
        report = preflight_tilemap_assets(self.root, self.request, self.architecture, self.candidates(), self.root / "preflight")
        check = next(item for item in report.checks if item.check_id == "object-opaque-background")
        self.assertEqual(check.status, QualityStatus.FAILED)

    def test_changed_candidate_invalidates_accepted_review(self) -> None:
        report = preflight_tilemap_assets(self.root, self.request, self.architecture, self.candidates(), self.root / "first")
        decisions = tuple(PreassemblyAssetDecision(item.asset_id, PreassemblyReviewStatus.ACCEPTED, "visual-pass", "accepted") for item in report.candidates)
        review = record_preassembly_review(report, decisions, "2026-08-09T00:00:00Z")
        self.foundation.write_bytes(self.foundation.read_bytes() + b"change")
        changed = preflight_tilemap_assets(self.root, self.request, self.architecture, self.candidates(), self.root / "second")
        with self.assertRaisesRegex(ValueError, "candidate hashes"):
            validate_preassembly_review(changed, review)

    def test_record_asset_review_writes_rejected_review_without_job_rejection(self) -> None:
        from game_visual_forge.cli.tilemap import run_tilemap_record_asset_review

        out = self.root / "preflight"
        report = preflight_tilemap_assets(self.root, self.request, self.architecture, self.candidates(), out)
        decisions = self.root / "decisions.json"
        decisions.write_text(json.dumps({"schema_version": 1, "assets": [{"asset_id": item.asset_id, "status": "rejected", "reason_code": "visual-fail", "reason": "replace"} for item in report.candidates]}), encoding="utf-8")
        result = run_tilemap_record_asset_review(out / "critical-assets-report.json", decisions, self.root / "review.json", "2026-08-09T00:00:00Z")
        self.assertEqual(result["status"], "rejected")
        self.assertTrue((self.root / "review.json").is_file())


if __name__ == "__main__":
    unittest.main()
