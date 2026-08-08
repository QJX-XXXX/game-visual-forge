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
from game_visual_forge.processing.tilemap_atlas_normalization import normalize_tilemap_atlases
from game_visual_forge.processing.tilemap_asset_preflight import preflight_tilemap_assets
from game_visual_forge.routing import select_tilemap_architecture
from tests.test_normalize_tile_atlas import make_request, native_decision


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

    def test_native_normalization_report_is_bound_to_preflight_candidates(self) -> None:
        request = make_request()
        decision = native_decision(request)
        architecture = select_tilemap_architecture(request, fingerprint_request(request.to_dict()))
        source = self.root / "generated-atlas.png"
        Image.new("RGBA", (1024, 1024), (50, 90, 120, 255)).save(source)
        pages = (("page-01", source), ("page-02", source), ("page-03", source))
        normalization = normalize_tilemap_atlases(self.root, request, decision, pages, self.root / "normalized")

        report = preflight_tilemap_assets(
            self.root,
            request,
            architecture,
            tuple((page.atlas_id, "atlas", self.root / page.output_path) for page in normalization.pages),
            self.root / "normalized-preflight",
            decision=decision,
            normalization_report=normalization,
            normalization_report_path=self.root / "normalized" / "atlas-normalization-report.json",
        )

        self.assertEqual(report.deterministic_status, QualityStatus.PASSED)
        self.assertEqual(report.normalization_report_path, "normalized/atlas-normalization-report.json")
        self.assertEqual(len(report.normalization_report_sha256 or ""), 64)

    def test_native_preflight_rejects_missing_normalization_report(self) -> None:
        request = make_request()
        decision = native_decision(request)
        architecture = select_tilemap_architecture(request, fingerprint_request(request.to_dict()))
        source = self.root / "generated-atlas.png"
        Image.new("RGBA", (128, 128), (50, 90, 120, 255)).save(source)
        pages = tuple((page.atlas_id, "atlas", source) for page in request.resolved_atlas_pages)

        with self.assertRaisesRegex(ValueError, "normalization report"):
            preflight_tilemap_assets(self.root, request, architecture, pages, self.root / "missing-report", decision=decision)


if __name__ == "__main__":
    unittest.main()
