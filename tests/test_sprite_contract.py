from __future__ import annotations

import unittest

from tests._bootstrap import ROOT  # noqa: F401
from game_visual_forge.contracts import (
    BackgroundRemoval,
    SpriteLayout,
    SpriteOutput,
    SpriteRequest,
    SpriteSourcePreference,
)


def make_request() -> SpriteRequest:
    return SpriteRequest(
        schema_version=1,
        asset_id="hero-run",
        prompt="A side-view swordswoman running in place.",
        output_dir="outputs/hero-run",
        source_preference=SpriteSourcePreference.AUTO,
        canvas_width=1024,
        canvas_height=1024,
        layout=SpriteLayout.GRID,
        frame_count=8,
        directions=("right",),
        outputs=(SpriteOutput.FRAMES, SpriteOutput.SHEET, SpriteOutput.GIF),
        reference_paths=("references/hero.png",),
        style_constraints=("clean HD game art",),
        identity_constraints=("same armor in every frame",),
        action_name="run",
        frame_width=256,
        frame_height=256,
        grid_rows=2,
        grid_columns=4,
        background_removal=BackgroundRemoval.CHROMA,
        chroma_color="#ff00ff",
        target_engine_notes="Unity pixels-per-unit 100",
    )


class SpriteRequestTests(unittest.TestCase):
    def test_request_round_trip_is_exact(self) -> None:
        request = make_request()
        self.assertEqual(SpriteRequest.from_dict(request.to_dict()), request)

    def test_grid_capacity_must_cover_frame_count(self) -> None:
        payload = make_request().to_dict()
        payload["grid_columns"] = 3
        with self.assertRaisesRegex(ValueError, "grid capacity"):
            SpriteRequest.from_dict(payload)

    def test_bool_is_not_accepted_as_integer(self) -> None:
        payload = make_request().to_dict()
        payload["frame_count"] = True
        with self.assertRaisesRegex(TypeError, "frame_count"):
            SpriteRequest.from_dict(payload)

    def test_absolute_and_parent_paths_are_rejected(self) -> None:
        for path in ("C:/secret.png", "/secret.png", "../secret.png"):
            payload = make_request().to_dict()
            payload["reference_paths"] = [path]
            with self.subTest(path=path):
                with self.assertRaisesRegex(ValueError, "reference_paths"):
                    SpriteRequest.from_dict(payload)

    def test_chroma_mode_requires_rgb_hex_color(self) -> None:
        payload = make_request().to_dict()
        payload["chroma_color"] = "magenta"
        with self.assertRaisesRegex(ValueError, "chroma_color"):
            SpriteRequest.from_dict(payload)


if __name__ == "__main__":
    unittest.main()
