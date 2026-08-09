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
from game_visual_forge.processing.video_probe import sha256_file
from game_visual_forge.processing.video_review import create_contact_sheet, create_motion_difference, create_anchor_diagnostic, record_video_motion_review
from game_visual_forge.processing.video_sprite import process_video_sprite
from game_visual_forge.quality.video import assess_video_outputs, build_video_asset_manifest, publish_video_outputs, validate_reviewed_video_outputs


class VideoQualityTests(unittest.TestCase):
    def test_temporal_warning_does_not_replace_hard_failure(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            source = source_record(root)
            request = VideoSpriteRequest.from_dict(valid_request(background_mode="preserve", frame_counts=[4], canvas_width=48, canvas_height=48, output_dir="outputs/static"))
            processing = process_video_sprite(root, request, source, make_raw_frames(root), frame_counts=(4,))
            report = assess_video_outputs(root, request, source, processing)
            self.assertEqual(report.deterministic_status, QualityStatus.PASSED)
            self.assertIn(report.temporal_status, {QualityStatus.PASSED, QualityStatus.NEEDS_ATTENTION})

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


if __name__ == "__main__":
    unittest.main()
