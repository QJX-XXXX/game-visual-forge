from __future__ import annotations

import unittest
from dataclasses import replace

from tests._bootstrap import ROOT  # noqa: F401
from game_visual_forge.contracts import (
    BackgroundRemoval,
    DeliveryAnchor,
    DeliveryNormalization,
    RembgRefinement,
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

    def test_missing_background_policy_defaults_to_native_transparency_auto(self) -> None:
        payload = make_request().to_dict()
        payload.pop("background_removal")
        payload["chroma_color"] = None

        request = SpriteRequest.from_dict(payload)

        self.assertEqual(request.background_removal, BackgroundRemoval.AUTO)

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

    def test_rembg_mode_accepts_chroma_fallback_color(self) -> None:
        payload = make_request().to_dict()
        payload["background_removal"] = "rembg"
        request = SpriteRequest.from_dict(payload)
        self.assertEqual(request.background_removal, BackgroundRemoval.REMBG)
        self.assertEqual(request.chroma_color, "#ff00ff")
        self.assertIsNone(request.rembg_refinement)

    def test_rembg_mode_accepts_explicit_pymatting_refinement(self) -> None:
        payload = make_request().to_dict()
        payload["background_removal"] = "rembg"
        payload["rembg_refinement"] = "pymatting"
        request = SpriteRequest.from_dict(payload)
        self.assertEqual(request.rembg_refinement, RembgRefinement.PYMATTING)

    def test_old_request_without_refinement_field_remains_compatible(self) -> None:
        payload = make_request().to_dict()
        payload.pop("rembg_refinement")
        request = SpriteRequest.from_dict(payload)
        self.assertIsNone(request.rembg_refinement)

    def test_delivery_normalization_round_trips(self) -> None:
        request = replace(
            make_request(),
            delivery_normalization=DeliveryNormalization(
                canvas_width=512,
                canvas_height=768,
                anchor=DeliveryAnchor.FEET,
                fit_scale=0.88,
            ),
        )
        restored = SpriteRequest.from_dict(request.to_dict())
        self.assertEqual(restored, request)

    def test_delivery_normalization_rejects_invalid_fit_scale(self) -> None:
        with self.assertRaisesRegex(ValueError, "fit_scale"):
            DeliveryNormalization(canvas_width=64, canvas_height=64, fit_scale=1.1)

    def test_refinement_requires_rembg_with_chroma_color(self) -> None:
        payload = make_request().to_dict()
        payload["rembg_refinement"] = "pymatting"
        with self.assertRaisesRegex(ValueError, "rembg_refinement"):
            SpriteRequest.from_dict(payload)

    def test_preserve_mode_rejects_chroma_color(self) -> None:
        payload = make_request().to_dict()
        payload["background_removal"] = "preserve"
        with self.assertRaisesRegex(ValueError, "chroma_color"):
            SpriteRequest.from_dict(payload)


if __name__ == "__main__":
    unittest.main()
