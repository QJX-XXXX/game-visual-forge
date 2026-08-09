from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests._bootstrap import ROOT
from tests.test_video_processing import make_raw_frames, source_record
from tests.test_video_contract import valid_request

from game_visual_forge.contracts.serialization import dump_json
from game_visual_forge.contracts.video import VideoSpriteRequest
from game_visual_forge.processing.video_review import create_contact_sheet, create_motion_difference, create_anchor_diagnostic, record_video_motion_review
from game_visual_forge.processing.video_sprite import process_video_sprite
from game_visual_forge.quality.video import assess_video_outputs, build_video_asset_manifest, publish_video_outputs, validate_reviewed_video_outputs


class VideoCleanWorkflowTests(unittest.TestCase):
    def test_existing_video_reaches_final_manifest_without_provider_events(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            source = source_record(root)
            request = VideoSpriteRequest.from_dict(valid_request(background_mode="chroma", chroma_color="#ff00ff", frame_counts=[4], canvas_width=48, canvas_height=48, output_dir="outputs/clean"))
            processing = process_video_sprite(root, request, source, make_raw_frames(root), frame_counts=(4,))
            staging = root / processing.staging_dir
            report = assess_video_outputs(root, request, source, processing)
            quality_path = staging / "video-quality-report.json"
            dump_json(quality_path, report.to_dict())
            preview = staging / "delivery" / "previews" / "density-4.gif"
            review = record_video_motion_review(root, source.request_fingerprint, source.sha256, quality_path, {"preview": preview}, {"action": True}, True, "2026-08-09T00:00:00Z")
            reviewed = validate_reviewed_video_outputs(root, request, source, processing, review, quality_path, {"preview": preview})
            manifest = build_video_asset_manifest(root, request, source, processing, reviewed)
            final = root / "outputs" / "clean-final"
            self.assertTrue(publish_video_outputs(staging, final, reviewed, manifest))
            self.assertTrue((final / "asset-manifest.json").is_file())


if __name__ == "__main__":
    unittest.main()
