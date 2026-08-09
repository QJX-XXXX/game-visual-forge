from __future__ import annotations

import unittest

from tests._bootstrap import ROOT

from game_visual_forge.contracts.video import (
    VideoBackgroundMode,
    VideoGenerationMode,
    VideoProcessingMode,
    VideoSourcePreference,
    VideoSpriteRequest,
)


def valid_request(**overrides):
    value = {
        "schema_version": 1,
        "asset_id": "walk-cycle",
        "action_name": "walk",
        "prompt": "A character walks in place",
        "output_dir": "outputs/walk-cycle",
        "source_preference": "existing-file",
        "existing_video_path": "inputs/walk.mp4",
        "generation_mode": "t2v",
        "loop": True,
        "clip_start_seconds": 0.0,
        "clip_end_seconds": 1.0,
        "frame_counts": [24],
        "outputs": ["frames", "strips", "sheets", "gif"],
        "background_mode": "rembg",
        "chroma_color": None,
        "rembg_refinement": None,
        "processing_mode": "hd",
        "canvas_width": 128,
        "canvas_height": 128,
        "anchor": "feet",
        "fit_scale": 0.88,
        "reference_paths": [],
        "target_engine_notes": "Unity",
    }
    value.update(overrides)
    return value


class VideoContractTests(unittest.TestCase):
    def test_request_normalizes_frame_counts_and_defaults(self) -> None:
        request = VideoSpriteRequest.from_dict(valid_request(frame_counts=[24, 8, 24, 16]))
        self.assertEqual(request.frame_counts, (8, 16, 24))
        self.assertEqual(request.background_mode, VideoBackgroundMode.REMBG)
        self.assertEqual(request.source_preference, VideoSourcePreference.EXISTING_FILE)

    def test_default_density_is_24(self) -> None:
        request = VideoSpriteRequest.from_dict(valid_request(frame_counts=None))
        self.assertEqual(request.frame_counts, (24,))

    def test_loop_interval_must_increase(self) -> None:
        with self.assertRaisesRegex(ValueError, "clip_end_seconds"):
            VideoSpriteRequest.from_dict(valid_request(clip_start_seconds=2.0, clip_end_seconds=2.0))

    def test_non_t2v_requires_reference_for_image_to_video(self) -> None:
        with self.assertRaisesRegex(ValueError, "first_frame_path"):
            VideoSpriteRequest.from_dict(valid_request(generation_mode="i2v-first"))

    def test_contract_paths_reject_absolute_and_parent_segments(self) -> None:
        for value in ("C:/secret/video.mp4", "../video.mp4", "/tmp/video.mp4"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                VideoSpriteRequest.from_dict(valid_request(existing_video_path=value))

    def test_serialization_round_trip(self) -> None:
        request = VideoSpriteRequest.from_dict(valid_request())
        restored = VideoSpriteRequest.from_dict(request.to_dict())
        self.assertEqual(restored, request)

    def test_frame_count_safety_limit(self) -> None:
        with self.assertRaisesRegex(ValueError, "frame_counts"):
            VideoSpriteRequest.from_dict(valid_request(frame_counts=[241]))


if __name__ == "__main__":
    unittest.main()
