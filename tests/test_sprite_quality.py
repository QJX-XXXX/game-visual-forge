from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from PIL import Image

from tests._bootstrap import ROOT  # noqa: F401
from game_visual_forge.contracts import (
    DeliveryAnchor,
    DeliveryNormalization,
    QualityStatus,
    SourceType,
)
from game_visual_forge.processing.images import ingest_image
from game_visual_forge.processing.sprite import ProcessingResult
from game_visual_forge.quality import apply_visual_review, build_asset_manifest, validate_sprite_outputs
from tests.test_sprite_contract import make_request


class SpriteQualityTests(unittest.TestCase):
    def make_data(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        staging = root / "outputs" / ".hero-run.staging"
        (staging / "frames").mkdir(parents=True)
        source = root / "source.png"
        Image.new("RGBA", (8, 8), (255, 0, 255, 255)).save(source)
        for name in ("frame-000.png", "frame-001.png"):
            Image.new("RGBA", (4, 4), (0, 0, 0, 0)).save(staging / "frames" / name)
        request = replace(make_request(), canvas_width=8, canvas_height=8, frame_count=2, grid_rows=1, grid_columns=2)
        record = ingest_image(root, source, SourceType.EXISTING_FILE, "a" * 64)
        processing = ProcessingResult(1, "outputs/.hero-run.staging", ("frames/frame-000.png", "frames/frame-001.png"), None, None, ("verify-source",), False)
        return root, staging, request, record, processing

    def test_report_separates_deterministic_and_visual_review(self) -> None:
        root, staging, request, record, processing = self.make_data()
        report = validate_sprite_outputs(staging, request, record, processing)
        self.assertEqual(report.deterministic_status, QualityStatus.FAILED)
        self.assertEqual(report.visual_status, QualityStatus.NEEDS_VISUAL_REVIEW)
        self.assertEqual(len(report.visual_checks), 6)

    def test_visual_review_requires_all_checks_and_round_trips(self) -> None:
        root, staging, request, record, processing = self.make_data()
        report = validate_sprite_outputs(staging, request, record, processing)
        payload = {"schema_version": 1, "checks": {item.check_id: "passed" for item in report.visual_checks}}
        reviewed = apply_visual_review(report, payload)
        self.assertEqual(reviewed.visual_status, QualityStatus.PASSED)
        self.assertEqual(type(reviewed).from_dict(reviewed.to_dict()), reviewed)
        with self.assertRaisesRegex(ValueError, "every required"):
            apply_visual_review(report, {"schema_version": 1, "checks": {}})

    def test_manifest_records_source_and_output_hashes(self) -> None:
        root, staging, request, record, processing = self.make_data()
        report = validate_sprite_outputs(staging, request, record, processing)
        manifest = build_asset_manifest(staging, request, record, processing, report)
        self.assertEqual(len(manifest.artifacts), 3)
        self.assertEqual(manifest.artifacts[0].role, "source")
        self.assertEqual(len({item.path for item in manifest.artifacts}), 3)

    def test_manifest_records_delivery_normalization_metadata(self) -> None:
        root, staging, request, record, processing = self.make_data()
        delivery_dir = staging / "delivery" / "frames"
        delivery_dir.mkdir(parents=True)
        Image.new("RGBA", (16, 20), (0, 0, 0, 0)).save(delivery_dir / "frame-000.png")
        processing = replace(
            processing,
            delivery_frame_paths=("delivery/frames/frame-000.png",),
            delivery_metadata={
                "canvas_width": 16,
                "canvas_height": 20,
                "anchor": "feet",
                "fit_scale": 0.8,
                "scale": 2.0,
                "source_bounds": [[0, 0, 4, 4]],
            },
        )
        request = replace(
            request,
            delivery_normalization=DeliveryNormalization(
                canvas_width=16,
                canvas_height=20,
                anchor=DeliveryAnchor.FEET,
                fit_scale=0.8,
            ),
        )
        report = validate_sprite_outputs(staging, request, record, processing)
        manifest = build_asset_manifest(staging, request, record, processing, report)
        self.assertEqual(manifest.delivery_normalization, processing.delivery_metadata)
        self.assertEqual(manifest.artifacts[-1].role, "delivery-frame")


if __name__ == "__main__":
    unittest.main()
