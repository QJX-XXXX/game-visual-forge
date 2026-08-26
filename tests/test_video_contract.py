from __future__ import annotations

import unittest

from tests._bootstrap import ROOT

from game_visual_forge.contracts.video import (
    VideoBackgroundMode,
    VideoGenerationMode,
    VideoLayoutMode,
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
        self.assertEqual(request.layout_mode, VideoLayoutMode.TIGHT)

    def test_request_accepts_reference_locked_layout(self) -> None:
        request = VideoSpriteRequest.from_dict(valid_request(layout_mode="reference-locked"))
        self.assertEqual(request.layout_mode, VideoLayoutMode.REFERENCE_LOCKED)
        self.assertEqual(request.to_dict()["layout_mode"], "reference-locked")

    def test_request_accepts_comfyui_h3_as_a_video_source(self) -> None:
        try:
            request = VideoSpriteRequest.from_dict(
                valid_request(
                    source_preference="comfyui-h3",
                    existing_video_path=None,
                    backend="comfy-mcp",
                )
            )
        except ValueError as error:
            self.fail(f"comfyui-h3 should be a supported video source: {error}")
        self.assertEqual(request.source_preference.value, "comfyui-h3")

    def test_default_density_is_24(self) -> None:
        request = VideoSpriteRequest.from_dict(valid_request(frame_counts=None))
        self.assertEqual(request.frame_counts, (24,))

    def test_loop_interval_must_increase(self) -> None:
        with self.assertRaisesRegex(ValueError, "clip_end_seconds"):
            VideoSpriteRequest.from_dict(valid_request(clip_start_seconds=2.0, clip_end_seconds=2.0))

    def test_non_t2v_requires_reference_for_image_to_video(self) -> None:
        with self.assertRaisesRegex(ValueError, "first_frame_path"):
            VideoSpriteRequest.from_dict(valid_request(generation_mode="i2v-first"))

    def test_h3_last_frame_mode_requires_and_accepts_a_last_frame(self) -> None:
        with self.assertRaisesRegex(ValueError, "last_frame_path"):
            VideoSpriteRequest.from_dict(valid_request(generation_mode="i2v-last"))
        try:
            request = VideoSpriteRequest.from_dict(
                valid_request(
                    generation_mode="i2v-last",
                    last_frame_path="inputs/walk-last.png",
                )
            )
        except ValueError as error:
            self.fail(f"i2v-last should be supported when a last frame is supplied: {error}")
        self.assertEqual(request.generation_mode.value, "i2v-last")

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
