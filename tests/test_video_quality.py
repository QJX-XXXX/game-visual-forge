from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests._bootstrap import ROOT
from tests.test_video_processing import make_raw_frames, source_record
from tests.test_video_contract import valid_request

from game_visual_forge.contracts.quality import QualityStatus
from game_visual_forge.contracts.serialization import dump_json
from game_visual_forge.contracts.video import VideoSpriteRequest
from game_visual_forge.contracts.video_quality import VideoQualityReport
from game_visual_forge.processing.video_probe import sha256_file
from game_visual_forge.processing.video_review import create_contact_sheet, create_motion_difference, create_anchor_diagnostic, record_video_motion_review
from game_visual_forge.processing.video_sprite import process_video_sprite
from game_visual_forge.quality.video import _visible_chroma_residue_percent, assess_video_outputs, build_video_asset_manifest, publish_video_outputs, validate_reviewed_video_outputs


class VideoQualityTests(unittest.TestCase):
    def test_temporal_warning_does_not_replace_hard_failure(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            source = source_record(root)
            request = VideoSpriteRequest.from_dict(valid_request(background_mode="preserve", canvas_policy="report-only", frame_counts=[4], canvas_width=48, canvas_height=48, output_dir="outputs/static"))
            processing = process_video_sprite(root, request, source, make_raw_frames(root), frame_counts=(4,))
            report = assess_video_outputs(root, request, source, processing)
            self.assertEqual(report.deterministic_status, QualityStatus.PASSED)
            self.assertIn(report.temporal_status, {QualityStatus.PASSED, QualityStatus.NEEDS_ATTENTION})

    def test_canvas_containment_is_a_deterministic_publication_gate(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            source = source_record(root)
            request = VideoSpriteRequest.from_dict(valid_request(background_mode="chroma", chroma_color="#ff00ff", frame_counts=[4], canvas_width=48, canvas_height=48, safe_frame_margin=0.1, output_dir="outputs/unsafe"))
            processing = process_video_sprite(root, request, source, make_raw_frames(root), frame_counts=(4,))
            from PIL import Image, ImageDraw
            unsafe = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
            ImageDraw.Draw(unsafe).rectangle((0, 12, 10, 32), fill=(255, 255, 255, 255))
            unsafe.save(root / processing.artifacts["frames:4"] / "frame-000.png")
            report = assess_video_outputs(root, request, source, processing)
            containment = next(item for item in report.deterministic_checks if item.check_id == "canvas-containment")
            self.assertEqual(containment.status, QualityStatus.FAILED)
            self.assertEqual(report.deterministic_status, QualityStatus.FAILED)
            self.assertEqual(report.canvas_containment["status"], "failed")
            self.assertIn("swept_bounds", report.canvas_containment)
            manifest = build_video_asset_manifest(root, request, source, processing, report)
            self.assertFalse(publish_video_outputs(root / processing.staging_dir, root / request.output_dir, report, manifest))

    def test_tight_trim_keeps_source_edge_evidence(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            source = source_record(root)
            request = VideoSpriteRequest.from_dict(valid_request(background_mode="chroma", chroma_color="#ff00ff", frame_counts=[4], canvas_width=48, canvas_height=48, output_dir="outputs/source-edge"))
            raw_frames = list(make_raw_frames(root))
            from PIL import Image, ImageDraw
            raw_path = root / raw_frames[0].raw_path
            with Image.open(raw_path).convert("RGBA") as image:
                ImageDraw.Draw(image).rectangle((0, 10, 4, 22), fill=(255, 255, 255, 255))
                image.save(raw_path)
            processing = process_video_sprite(root, request, source, tuple(raw_frames), frame_counts=(4,))
            report = assess_video_outputs(root, request, source, processing)
            self.assertEqual(report.canvas_containment["source_edge_contact_frames"], [0])
            self.assertEqual(report.canvas_containment["status"], "failed")

    def test_containment_checks_all_requested_densities(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            source = source_record(root)
            request = VideoSpriteRequest.from_dict(valid_request(background_mode="chroma", chroma_color="#ff00ff", frame_counts=[2, 4], canvas_width=48, canvas_height=48, safe_frame_margin=0.1, output_dir="outputs/all-density-containment"))
            processing = process_video_sprite(root, request, source, make_raw_frames(root), frame_counts=(2, 4))
            from PIL import Image, ImageDraw
            unsafe = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
            ImageDraw.Draw(unsafe).rectangle((0, 12, 8, 30), fill=(255, 255, 255, 255))
            unsafe.save(root / processing.artifacts["frames:2"] / "frame-000.png")
            report = assess_video_outputs(root, request, source, processing)
            self.assertEqual(report.canvas_containment["densities"]["2"]["passed"], False)
            self.assertEqual(report.deterministic_status, QualityStatus.FAILED)

    def test_preserved_background_containment_is_explicitly_unevaluable(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            source = source_record(root)
            request = VideoSpriteRequest.from_dict(valid_request(background_mode="preserve", canvas_policy="report-only", frame_counts=[4], canvas_width=48, canvas_height=48, output_dir="outputs/preserved"))
            processing = process_video_sprite(root, request, source, make_raw_frames(root), frame_counts=(4,))
            report = assess_video_outputs(root, request, source, processing)
            self.assertFalse(report.canvas_containment["foreground_evaluable"])
            self.assertEqual(report.canvas_containment["status"], "needs_attention")
            self.assertNotEqual(report.deterministic_status, QualityStatus.FAILED)

    def test_strict_preserved_background_blocks_publication(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            source = source_record(root)
            request = VideoSpriteRequest.from_dict(valid_request(background_mode="preserve", frame_counts=[4], canvas_width=48, canvas_height=48, output_dir="outputs/preserved-strict"))
            processing = process_video_sprite(root, request, source, make_raw_frames(root), frame_counts=(4,))
            report = assess_video_outputs(root, request, source, processing)
            self.assertEqual(report.canvas_containment["status"], "failed")
            self.assertEqual(report.deterministic_status, QualityStatus.FAILED)

    def test_review_requires_explicit_containment_checks(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            source = source_record(root)
            request = VideoSpriteRequest.from_dict(valid_request(background_mode="chroma", chroma_color="#ff00ff", frame_counts=[4], canvas_width=48, canvas_height=48, output_dir="outputs/review-checks"))
            processing = process_video_sprite(root, request, source, make_raw_frames(root), frame_counts=(4,))
            quality_path = root / processing.staging_dir / "video-quality-report.json"
            dump_json(quality_path, assess_video_outputs(root, request, source, processing).to_dict())
            preview = root / processing.artifacts["gif:4"]
            review = record_video_motion_review(root, source.request_fingerprint, source.sha256, quality_path, {"preview": preview}, {"action": True}, True, "2026-08-09T00:00:00Z")
            with self.assertRaisesRegex(ValueError, "missing required checks"):
                validate_reviewed_video_outputs(root, request, source, processing, review, quality_path, {"preview": preview})

    def test_legacy_report_without_containment_field_deserializes(self) -> None:
        legacy = {
            "schema_version": 1,
            "asset_id": "legacy",
            "request_fingerprint": "a" * 64,
            "deterministic_status": "passed",
            "temporal_status": "passed",
            "visual_status": "needs_visual_review",
            "deterministic_checks": [],
            "temporal_metrics": {},
            "visual_checks": {},
        }
        report = VideoQualityReport.from_dict(legacy)
        self.assertEqual(report.canvas_containment, {})

    def test_publish_requires_current_approved_review(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            source = source_record(root)
            request = VideoSpriteRequest.from_dict(valid_request(background_mode="chroma", chroma_color="#ff00ff", frame_counts=[4], canvas_width=48, canvas_height=48, output_dir="outputs/valid"))
            processing = process_video_sprite(root, request, source, make_raw_frames(root), frame_counts=(4,))
            staging = root / processing.staging_dir
            pre_report = assess_video_outputs(root, request, source, processing)
            quality_path = staging / "video-quality-report.json"
            dump_json(quality_path, pre_report.to_dict())
            preview = staging / "delivery" / "previews" / "density-4.gif"
            review = record_video_motion_review(root, source.request_fingerprint, source.sha256, quality_path, {"preview": preview}, {"action": True}, True, "2026-08-09T00:00:00Z")
            preview.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "stale"):
                validate_reviewed_video_outputs(root, request, source, processing, review, quality_path, {"preview": preview})

    def test_visible_chroma_residue_blocks_transparent_margin_false_positive(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            source = source_record(root)
            request = VideoSpriteRequest.from_dict(valid_request(background_mode="chroma", chroma_color="#ff00ff", frame_counts=[4], canvas_width=48, canvas_height=48, output_dir="outputs/residue"))
            processing = process_video_sprite(root, request, source, make_raw_frames(root), frame_counts=(4,))
            from PIL import Image
            frame_dir = root / processing.artifacts["frames:4"]
            for path in frame_dir.glob("frame-*.png"):
                image = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
                for x in range(4, 44):
                    for y in range(4, 44):
                        image.putpixel((x, y), (254, 0, 253, 255))
                image.save(path)
            report = assess_video_outputs(root, request, source, processing)
            residue = next(item for item in report.deterministic_checks if item.check_id == "chroma-residue")
            self.assertEqual(residue.status, QualityStatus.FAILED)
            self.assertEqual(report.deterministic_status, QualityStatus.FAILED)

    def test_chroma_residue_checks_lower_density_not_only_highest(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            source = source_record(root)
            request = VideoSpriteRequest.from_dict(valid_request(background_mode="chroma", chroma_color="#ff00ff", frame_counts=[2, 4], canvas_width=48, canvas_height=48, output_dir="outputs/all-density-residue"))
            processing = process_video_sprite(root, request, source, make_raw_frames(root), frame_counts=(2, 4))
            low_path = root / processing.artifacts["frames:2"] / "frame-000.png"
            from PIL import Image
            Image.new("RGBA", (48, 48), (255, 0, 255, 255)).save(low_path)
            report = assess_video_outputs(root, request, source, processing)
            check = next(item for item in report.deterministic_checks if item.check_id == "chroma-residue")
            self.assertEqual(check.status, QualityStatus.FAILED)
            self.assertIn("density 2", check.message)

    def test_chroma_residue_uses_configured_non_magenta_key(self) -> None:
        from PIL import Image
        image = Image.new("RGBA", (10, 10), (0, 255, 0, 255))
        self.assertEqual(_visible_chroma_residue_percent(image, "#00ff00"), 100.0)

    def test_chroma_residue_threshold_allows_one_percent_and_rejects_more(self) -> None:
        from PIL import Image
        image = Image.new("RGBA", (10, 10), (255, 255, 255, 255))
        image.putpixel((0, 0), (254, 0, 253, 255))
        self.assertEqual(_visible_chroma_residue_percent(image, "#ff00ff"), 1.0)
        image.putpixel((1, 0), (254, 0, 253, 255))
        self.assertGreater(_visible_chroma_residue_percent(image, "#ff00ff"), 1.0)

    def test_failed_chroma_residue_prevents_publication(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            source = source_record(root)
            request = VideoSpriteRequest.from_dict(valid_request(background_mode="chroma", chroma_color="#ff00ff", frame_counts=[4], canvas_width=48, canvas_height=48, output_dir="outputs/publication-block"))
            processing = process_video_sprite(root, request, source, make_raw_frames(root), frame_counts=(4,))
            from PIL import Image
            Image.new("RGBA", (48, 48), (255, 0, 255, 255)).save(root / processing.artifacts["frames:4"] / "frame-000.png")
            report = assess_video_outputs(root, request, source, processing)
            manifest = build_video_asset_manifest(root, request, source, processing, report)
            self.assertEqual(report.deterministic_status, QualityStatus.FAILED)
            self.assertFalse(publish_video_outputs(root / processing.staging_dir, root / request.output_dir, report, manifest))


if __name__ == "__main__":
    unittest.main()
