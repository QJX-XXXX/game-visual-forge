from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw, ImageFilter

from tests._bootstrap import ROOT  # noqa: F401
from game_visual_forge.contracts import (
    BackgroundRemoval,
    DeliveryAnchor,
    DeliveryNormalization,
    RembgRefinement,
    SpriteOutput,
)
from game_visual_forge.processing.background import (
    BackgroundResult,
    DEFAULT_REMBG_MODEL,
    DIRECT_ONNX_REMBG_MODELS,
    _run_rembg_attempt,
    clean_rembg_chroma_residue,
    remove_background,
    remove_chroma,
)
from game_visual_forge.processing.matting import (
    hybrid_chroma_fusion,
    measure_chroma_residue,
    reconstruct_known_background,
)
from game_visual_forge.processing.frames import split_grid, trim_alpha
from game_visual_forge.processing.alignment import align_bottom_center
from game_visual_forge.processing.sprite import process_sprite
from game_visual_forge.processing.images import ingest_image
from tests.test_sprite_contract import make_request


class SpriteProcessingTests(unittest.TestCase):
    def make_image(self, root: Path) -> Path:
        path = root / "raw" / "source.png"
        path.parent.mkdir()
        image = Image.new("RGBA", (8, 8), (255, 0, 255, 255))
        draw = ImageDraw.Draw(image)
        for row in range(2):
            for column in range(2):
                left, top = column * 4, row * 4
                draw.rectangle((left + 1, top + 1, left + 2 + column, top + 2 + row), fill=(20, 30, 40, 255))
        image.save(path)
        return path

    def request(self):
        return replace(
            make_request(), canvas_width=8, canvas_height=8, frame_count=4,
            grid_rows=2, grid_columns=2, frame_width=4, frame_height=4,
            directions=("right",), outputs=(SpriteOutput.FRAMES, SpriteOutput.SHEET, SpriteOutput.GIF),
        )

    def test_chroma_split_trim_and_alignment_are_deterministic(self) -> None:
        image = Image.new("RGBA", (8, 8), (255, 0, 255, 255))
        image.putpixel((1, 1), (1, 2, 3, 255))
        processed = remove_chroma(image, "#ff00ff", tolerance=0)
        self.assertEqual(processed.getpixel((0, 0))[3], 0)
        with self.assertRaisesRegex(Exception, "empty"):
            split_grid(processed, rows=2, columns=2, frame_count=4)
        frame = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
        frame.putpixel((1, 1), (1, 2, 3, 255))
        aligned = align_bottom_center((trim_alpha(frame),))
        self.assertEqual(aligned[0].size, (1, 1))

    def test_high_detail_direct_models_use_1024_input(self) -> None:
        self.assertEqual(DEFAULT_REMBG_MODEL, "birefnet-general")
        self.assertEqual(
            DIRECT_ONNX_REMBG_MODELS["isnet-anime"].input_size,
            (1024, 1024),
        )
        self.assertEqual(
            DIRECT_ONNX_REMBG_MODELS["birefnet-general"].input_size,
            (1024, 1024),
        )
        self.assertTrue(
            DIRECT_ONNX_REMBG_MODELS["birefnet-general"].apply_sigmoid
        )

    def test_process_exports_frames_sheet_and_gif(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.make_image(root)
            request = self.request()
            record = ingest_image(root, source, request_source_type(request), "a" * 64)
            result = process_sprite(root, request, record, root / request.output_dir)
            staging = root / result.staging_dir
            self.assertEqual(len(result.frame_paths), 4)
            self.assertTrue((staging / "sprite-sheet.png").is_file())
            self.assertTrue((staging / "preview.gif").is_file())
            sizes = set()
            for path in result.frame_paths:
                with Image.open(staging / path) as frame:
                    sizes.add(frame.size)
            self.assertEqual(len(sizes), 1)

    def test_delivery_normalization_preserves_original_and_exports_delivery_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.make_image(root)
            request = replace(
                self.request(),
                delivery_normalization=DeliveryNormalization(
                    canvas_width=16,
                    canvas_height=20,
                    anchor=DeliveryAnchor.FEET,
                    fit_scale=0.8,
                ),
            )
            record = ingest_image(root, source, request_source_type(request), "a" * 64)
            result = process_sprite(root, request, record, root / request.output_dir)
            staging = root / result.staging_dir

            self.assertEqual(len(result.frame_paths), 4)
            self.assertEqual(len(result.delivery_frame_paths), 4)
            self.assertTrue((staging / "frames" / "frame-000.png").is_file())
            self.assertTrue((staging / "delivery" / "frames" / "frame-000.png").is_file())
            self.assertTrue((staging / "delivery" / "sprite-sheet.png").is_file())
            self.assertTrue((staging / "delivery" / "preview.gif").is_file())
            with Image.open(staging / result.delivery_frame_paths[0]) as frame:
                self.assertEqual(frame.size, (16, 20))
            self.assertEqual(result.delivery_metadata["anchor"], "feet")
            self.assertIn("delivery-normalize-feet", result.processing_steps)

    def test_missing_rembg_preserves_background_with_attention_flag(self) -> None:
        request = replace(self.request(), background_removal=BackgroundRemoval.REMBG, chroma_color=None)
        with patch("game_visual_forge.processing.background._load_rembg", return_value=None):
            result = remove_background(Image.new("RGBA", (2, 2), (1, 2, 3, 255)), request)
        self.assertEqual(result.method, "preserve-background")
        self.assertTrue(result.needs_attention)

    def test_rembg_prefers_cuda_before_cpu(self) -> None:
        image = Image.new("RGBA", (2, 2), (1, 2, 3, 255))
        request = replace(
            self.request(),
            background_removal=BackgroundRemoval.REMBG,
            chroma_color="#ff00ff",
        )
        calls = []

        def run_attempt(source, provider, *, model, timeout_seconds):
            calls.append(provider)
            return source, provider

        with (
            patch(
                "game_visual_forge.processing.background._load_rembg",
                return_value=object(),
            ),
            patch(
                "game_visual_forge.processing.background._available_onnx_providers",
                return_value=(
                    "CUDAExecutionProvider",
                    "CPUExecutionProvider",
                ),
            ),
            patch(
                "game_visual_forge.processing.background._run_rembg_attempt",
                side_effect=run_attempt,
            ),
        ):
            result = remove_background(image, request)

        self.assertEqual(
            result.method,
            "rembg-birefnet-general-cuda+hybrid-known-background",
        )
        self.assertFalse(result.needs_attention)
        self.assertEqual(calls, ["CUDAExecutionProvider"])

    def test_rembg_falls_back_from_cuda_to_cpu_before_chroma(self) -> None:
        image = Image.new("RGBA", (2, 2), (255, 0, 255, 255))
        image.putpixel((1, 1), (1, 2, 3, 255))
        request = replace(
            self.request(),
            background_removal=BackgroundRemoval.REMBG,
            chroma_color="#ff00ff",
        )
        calls = []

        def run_attempt(source, provider, *, model, timeout_seconds):
            calls.append(provider)
            if provider == "CUDAExecutionProvider":
                raise TimeoutError("cuda timeout")
            return source, provider

        with (
            patch(
                "game_visual_forge.processing.background._load_rembg",
                return_value=object(),
            ),
            patch(
                "game_visual_forge.processing.background._available_onnx_providers",
                return_value=(
                    "CUDAExecutionProvider",
                    "CPUExecutionProvider",
                ),
            ),
            patch(
                "game_visual_forge.processing.background._run_rembg_attempt",
                side_effect=run_attempt,
            ),
        ):
            result = remove_background(image, request)

        self.assertTrue(
            result.method.startswith(
                "rembg-birefnet-general-cpu-after-fallback"
            )
        )
        self.assertIn("cuda timeout", result.method)
        self.assertTrue(result.method.endswith("+hybrid-known-background"))
        self.assertFalse(result.needs_attention)
        self.assertEqual(calls, ["CUDAExecutionProvider", "CPUExecutionProvider"])

    def test_known_background_reconstruction_reduces_magenta_residue(self) -> None:
        raw = Image.new("RGBA", (64, 64), (255, 0, 255, 255))
        draw = ImageDraw.Draw(raw)
        draw.ellipse((12, 5, 52, 59), fill=(24, 30, 38, 255))
        draw.rectangle((30, 20, 34, 45), fill=(150, 15, 25, 255))

        raw = raw.filter(ImageFilter.GaussianBlur(1.2))
        mask = Image.new("L", raw.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((10, 3, 54, 61), fill=255)
        semantic = raw.copy()
        semantic.putalpha(mask.filter(ImageFilter.GaussianBlur(2.5)))

        hybrid = hybrid_chroma_fusion(raw, semantic, "#ff00ff")
        reconstructed = reconstruct_known_background(
            raw,
            hybrid,
            "#ff00ff",
        )

        hybrid_residue = measure_chroma_residue(hybrid, "#ff00ff")
        reconstructed_residue = measure_chroma_residue(
            reconstructed,
            "#ff00ff",
        )
        self.assertGreater(hybrid_residue["pixels"], 0)
        self.assertLess(
            reconstructed_residue["pixels"],
            hybrid_residue["pixels"],
        )
        self.assertLess(
            reconstructed_residue["pixel_ratio_percent"],
            hybrid_residue["pixel_ratio_percent"],
        )
        self.assertGreater(reconstructed.getpixel((32, 30))[0], 100)

    def test_chroma_residue_ratio_uses_visible_pixels_as_denominator(self) -> None:
        image = Image.new("RGBA", (2, 2), (255, 0, 255, 255))
        image.putpixel((1, 0), (20, 30, 40, 255))
        image.putpixel((1, 1), (255, 0, 255, 0))

        metrics = measure_chroma_residue(image, "#ff00ff")

        self.assertEqual(metrics["pixels"], 2)
        self.assertEqual(metrics["visible_pixels"], 3)
        self.assertEqual(metrics["pixel_ratio_percent"], 66.6667)

    def test_pymatting_is_only_used_when_explicitly_requested(self) -> None:
        image = Image.new("RGBA", (8, 8), (255, 0, 255, 255))
        semantic = Image.new("RGBA", image.size, (20, 30, 40, 255))
        request = replace(
            self.request(),
            background_removal=BackgroundRemoval.REMBG,
            chroma_color="#ff00ff",
            rembg_refinement=RembgRefinement.PYMATTING,
        )

        with patch(
            "game_visual_forge.processing.background._remove_rembg_with_fallbacks"
        ) as remove:
            remove.return_value = BackgroundResult(
                semantic,
                "rembg-birefnet-general-cuda",
                False,
            )
            with patch(
                "game_visual_forge.processing.matting.refine_with_pymatting",
                return_value=semantic,
            ) as refine:
                result = remove_background(image, request)

        refine.assert_called_once()
        self.assertEqual(
            result.method,
            "rembg-birefnet-general-cuda+hybrid-pymatting",
        )
        self.assertFalse(result.needs_attention)

    def test_pymatting_failure_falls_back_to_known_background(self) -> None:
        image = Image.new("RGBA", (8, 8), (255, 0, 255, 255))
        semantic = Image.new("RGBA", image.size, (20, 30, 40, 255))
        request = replace(
            self.request(),
            background_removal=BackgroundRemoval.REMBG,
            chroma_color="#ff00ff",
            rembg_refinement=RembgRefinement.PYMATTING,
        )

        with patch(
            "game_visual_forge.processing.background._remove_rembg_with_fallbacks"
        ) as remove:
            remove.return_value = BackgroundResult(
                semantic,
                "rembg-birefnet-general-cuda",
                False,
            )
            with patch(
                "game_visual_forge.processing.matting.refine_with_pymatting",
                side_effect=RuntimeError("solver failed"),
            ):
                result = remove_background(image, request)

        self.assertIn(
            "+hybrid-known-background-after-pymatting: solver failed",
            result.method,
        )
        self.assertTrue(result.needs_attention)

    def test_rembg_chroma_cleanup_removes_nearby_same_hue_fringe(self) -> None:
        image = Image.new("RGBA", (51, 51), (20, 30, 40, 255))
        image.putpixel((0, 0), (255, 0, 255, 255))
        image.putpixel((2, 2), (80, 4, 80, 255))
        image.putpixel((40, 40), (80, 4, 80, 255))
        image.putpixel((3, 3), (140, 20, 30, 255))

        result = clean_rembg_chroma_residue(image, "#ff00ff")

        self.assertEqual(result.getpixel((0, 0))[3], 0)
        self.assertLess(result.getpixel((2, 2))[3], 64)
        self.assertEqual(result.getpixel((40, 40))[3], 255)
        self.assertEqual(result.getpixel((3, 3))[3], 255)

    def test_rembg_attempt_drains_result_before_joining_worker(self) -> None:
        events = []
        output = Image.new("RGBA", (2, 2), (1, 2, 3, 255))
        payload = BytesIO()
        output.save(payload, format="PNG")
        payload.seek(0)

        class FakeQueue:
            def get(self, *, timeout):
                events.append(("get", timeout))
                return ("ok", payload.read(), "CPUExecutionProvider")

            def close(self):
                events.append(("close",))

        class FakeProcess:
            def start(self):
                events.append(("start",))

            def join(self, timeout):
                events.append(("join", timeout))

            def is_alive(self):
                return False

            def terminate(self):
                events.append(("terminate",))

        class FakeContext:
            def Queue(self, *, maxsize):
                self.result_queue = FakeQueue()
                return self.result_queue

            def Process(self, *, target, args):
                return FakeProcess()

        with patch(
            "game_visual_forge.processing.background.mp.get_context",
            return_value=FakeContext(),
        ):
            result, provider = _run_rembg_attempt(
                output,
                "CPUExecutionProvider",
                model="u2net",
                timeout_seconds=7,
            )

        self.assertEqual(provider, "CPUExecutionProvider")
        self.assertEqual(result.getpixel((0, 0)), (1, 2, 3, 255))
        self.assertLess(
            events.index(("get", 7)),
            events.index(("join", 5)),
        )

    def test_rembg_falls_back_to_chroma_after_gpu_and_cpu_fail(self) -> None:
        image = Image.new("RGBA", (2, 2), (238, 11, 238, 255))
        image.putpixel((1, 1), (1, 2, 3, 255))
        request = replace(
            self.request(),
            background_removal=BackgroundRemoval.REMBG,
            chroma_color="#ff00ff",
        )

        with (
            patch(
                "game_visual_forge.processing.background._load_rembg",
                return_value=object(),
            ),
            patch(
                "game_visual_forge.processing.background._available_onnx_providers",
                return_value=(
                    "CUDAExecutionProvider",
                    "CPUExecutionProvider",
                ),
            ),
            patch(
                "game_visual_forge.processing.background._run_rembg_attempt",
                side_effect=RuntimeError("failed"),
            ),
        ):
            result = remove_background(image, request)

        self.assertTrue(
            result.method.startswith(
                "chroma-fallback-after-rembg-birefnet-general-failed"
            )
        )
        self.assertIn("cuda:", result.method)
        self.assertIn("cpu:", result.method)
        self.assertTrue(result.needs_attention)
        self.assertEqual(result.image.getpixel((0, 0))[3], 0)
        self.assertEqual(result.image.getpixel((1, 1))[3], 255)

    def test_missing_rembg_uses_chroma_fallback_with_attention_flag(self) -> None:
        image = Image.new("RGBA", (2, 2), (255, 0, 255, 255))
        image.putpixel((1, 1), (20, 30, 40, 255))
        request = replace(
            self.request(),
            background_removal=BackgroundRemoval.REMBG,
            chroma_color="#ff00ff",
        )

        with patch(
            "game_visual_forge.processing.background._load_rembg",
            return_value=None,
        ):
            result = remove_background(image, request)

        self.assertEqual(result.method, "chroma-fallback")
        self.assertTrue(result.needs_attention)
        self.assertEqual(result.image.getpixel((0, 0))[3], 0)
        self.assertEqual(result.image.getpixel((1, 1))[3], 255)


def request_source_type(request):
    from game_visual_forge.contracts import SourceType
    return SourceType.EXISTING_FILE


if __name__ == "__main__":
    unittest.main()
