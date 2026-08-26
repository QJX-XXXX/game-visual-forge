from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests._bootstrap import ROOT

from game_visual_forge.contracts.video import VideoBackgroundMode, VideoSpriteRequest
from game_visual_forge.contracts.video import VideoSourceRecord
from game_visual_forge.processing.video_frames import build_sampling_plan
from game_visual_forge.processing.background import resize_rgba_alpha_safe
from game_visual_forge.processing.video_probe import sha256_file
from game_visual_forge.processing.video_sprite import process_video_sprite
from tests.test_video_contract import valid_request


def source_record(root: Path) -> VideoSourceRecord:
    source = root / "source.mp4"
    source.write_bytes(b"video")
    return VideoSourceRecord(1, "source.mp4", sha256_file(source), "mp4", "h264", 64, 64, 0, 1.0, "24/1", "24/1", False, 24, False, "a" * 64)


def make_raw_frames(root: Path, count: int = 4, background: tuple[int, int, int, int] = (255, 0, 255, 255)):
    from PIL import Image
    raw = root / "raw"
    raw.mkdir()
    records = []
    for index in range(count):
        image = Image.new("RGBA", (32, 32), background)
        for x in range(4 + index, 12 + index):
            for y in range(10, 26):
                image.putpixel((x, y), (255, 255, 255, 255))
        path = raw / f"frame-{index:04d}.png"
        image.save(path)
        from game_visual_forge.contracts.video import VideoFrameRecord
        records.append(VideoFrameRecord(1, index, index / count, None, path.relative_to(root).as_posix(), None, None, sha256_file(path)))
    return tuple(records)


class VideoProcessingTests(unittest.TestCase):
    def test_reference_locked_layout_keeps_first_frame_body_position(self) -> None:
        from PIL import Image

        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            raw = root / "locked-raw"
            raw.mkdir()
            records = []
            for index in range(2):
                image = Image.new("RGBA", (32, 32), (255, 0, 255, 255))
                for x in range(10, 18):
                    for y in range(10, 26):
                        image.putpixel((x, y), (255, 255, 255, 255))
                if index == 1:
                    for x in range(0, 32):
                        image.putpixel((x, 8), (80, 80, 80, 255))
                path = raw / f"frame-{index:04d}.png"
                image.save(path)
                from game_visual_forge.contracts.video import VideoFrameRecord
                records.append(VideoFrameRecord(1, index, index / 2, None, path.relative_to(root).as_posix(), None, None, sha256_file(path)))
            request = VideoSpriteRequest.from_dict(valid_request(background_mode="chroma", chroma_color="#ff00ff", layout_mode="reference-locked", frame_counts=[2], canvas_width=64, canvas_height=64, output_dir="outputs/locked"))
            result = process_video_sprite(root, request, source_record(root), tuple(records), frame_counts=(2,))
            outputs = [root / result.artifacts["frames:2"] / f"frame-{index:03d}.png" for index in range(2)]
            body_bounds = []
            for path in outputs:
                with Image.open(path).convert("RGBA") as image:
                    pixels = [(x, y) for y in range(image.height) for x in range(image.width) if image.getpixel((x, y))[:3] == (255, 255, 255) and image.getpixel((x, y))[3] > 0]
                    body_bounds.append((min(x for x, _ in pixels), min(y for _, y in pixels), max(x for x, _ in pixels) + 1, max(y for _, y in pixels) + 1))
            self.assertEqual(body_bounds[0], body_bounds[1])

    def test_reference_locked_layout_rejects_mixed_source_dimensions(self) -> None:
        from PIL import Image
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            raw = root / "mixed-raw"
            raw.mkdir()
            records = []
            for index, size in enumerate(((32, 32), (31, 32))):
                path = raw / f"frame-{index:04d}.png"
                Image.new("RGBA", size, (255, 255, 255, 255)).save(path)
                from game_visual_forge.contracts.video import VideoFrameRecord
                records.append(VideoFrameRecord(1, index, index / 2, None, path.relative_to(root).as_posix(), None, None, sha256_file(path)))
            request = VideoSpriteRequest.from_dict(valid_request(background_mode="preserve", layout_mode="reference-locked", frame_counts=[2], canvas_width=64, canvas_height=64, output_dir="outputs/mixed"))
            with self.assertRaisesRegex(ValueError, "same dimensions"):
                process_video_sprite(root, request, source_record(root), tuple(records), frame_counts=(2,))

    def test_chroma_cleanup_and_delivery_canvas(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            record = source_record(root)
            request = VideoSpriteRequest.from_dict(valid_request(background_mode="chroma", chroma_color="#ff00ff", frame_counts=[4], canvas_width=64, canvas_height=64, output_dir="outputs/walk"))
            result = process_video_sprite(root, request, record, make_raw_frames(root), frame_counts=(4,))
            self.assertFalse(result.needs_attention)
            self.assertEqual(len(result.frame_records), 4)
            from PIL import Image
            delivery = root / result.artifacts["frames:4"] / "frame-000.png"
            with Image.open(delivery) as image:
                self.assertEqual(image.size, (64, 64))
                self.assertEqual(image.getpixel((0, 0))[3], 0)

    def test_chroma_cleanup_accepts_codec_color_drift(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            record = source_record(root)
            request = VideoSpriteRequest.from_dict(valid_request(background_mode="chroma", chroma_color="#ff00ff", frame_counts=[4], canvas_width=64, canvas_height=64, output_dir="outputs/codec-drift"))
            result = process_video_sprite(root, request, record, make_raw_frames(root, background=(254, 0, 253, 255)), frame_counts=(4,))
            from PIL import Image
            delivery = root / result.artifacts["frames:4"] / "frame-000.png"
            with Image.open(delivery).convert("RGBA") as image:
                bounds = image.getchannel("A").getbbox()
            self.assertIsNotNone(bounds)
            assert bounds is not None
        self.assertLess(bounds[2] - bounds[0], 40)

    def test_chroma_cleanup_supports_non_magenta_codec_drift(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            record = source_record(root)
            request = VideoSpriteRequest.from_dict(valid_request(background_mode="chroma", chroma_color="#00ff00", processing_mode="hd", frame_counts=[4], canvas_width=64, canvas_height=64, output_dir="outputs/green-key"))
            result = process_video_sprite(root, request, record, make_raw_frames(root, background=(3, 252, 5, 255)), frame_counts=(4,))
            from PIL import Image
            with Image.open(root / result.artifacts["frames:4"] / "frame-000.png").convert("RGBA") as image:
                visible_green = sum(1 for red, green, blue, alpha in image.getdata() if alpha >= 8 and green > 180 and green > red + 60 and green > blue + 60)
            self.assertEqual(visible_green, 0)

    def test_hd_scaling_does_not_bleed_hidden_key_rgb(self) -> None:
        from PIL import Image
        image = Image.new("RGBA", (8, 8), (255, 0, 255, 0))
        for x in range(2, 6):
            for y in range(2, 6):
                image.putpixel((x, y), (240, 240, 240, 255))
        scaled = resize_rgba_alpha_safe(image, (31, 31), resample=Image.Resampling.LANCZOS)
        self.assertTrue(all(pixel[:3] == (0, 0, 0) for pixel in scaled.getdata() if pixel[3] == 0))
        self.assertFalse(any(red > 120 and blue > 120 and green < 80 and alpha > 0 for red, green, blue, alpha in scaled.getdata()))

    def test_pixel_mode_uses_one_canvas_for_every_frame(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            record = source_record(root)
            request = VideoSpriteRequest.from_dict(valid_request(background_mode="preserve", processing_mode="pixel", frame_counts=[4], canvas_width=48, canvas_height=48, output_dir="outputs/pixel"))
            result = process_video_sprite(root, request, record, make_raw_frames(root), frame_counts=(4,))
            from PIL import Image
            paths = [root / result.artifacts["frames:4"] / f"frame-{index:03d}.png" for index in range(4)]
            sizes = []
            for path in paths:
                with Image.open(path) as image:
                    sizes.append(image.size)
        self.assertEqual(set(sizes), {(48, 48)})

    def test_pixel_mode_still_uses_nearest_neighbor(self) -> None:
        from PIL import Image
        image = Image.new("RGBA", (2, 2), (0, 0, 0, 255))
        image.putpixel((0, 0), (255, 255, 255, 255))
        scaled = resize_rgba_alpha_safe(image, (8, 8), resample=Image.Resampling.NEAREST)
        visible_rgb = {pixel[:3] for pixel in scaled.getdata() if pixel[3] > 0}
        self.assertEqual(visible_rgb, {(255, 255, 255), (0, 0, 0)})

    def test_preserve_mode_keeps_opaque_source_background(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            request = VideoSpriteRequest.from_dict(valid_request(background_mode="preserve", processing_mode="hd", frame_counts=[4], canvas_width=48, canvas_height=48, output_dir="outputs/preserve-regression"))
            result = process_video_sprite(root, request, source_record(root), make_raw_frames(root), frame_counts=(4,))
            from PIL import Image
            with Image.open(root / result.artifacts["frames:4"] / "frame-000.png").convert("RGBA") as image:
                self.assertEqual(image.getpixel((24, 24))[3], 255)

    def test_rembg_callback_contract_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            request = VideoSpriteRequest.from_dict(valid_request(background_mode="rembg", chroma_color=None, processing_mode="hd", frame_counts=[4], output_dir="outputs/rembg-regression"))

            def remover(image, request):
                cleaned = image.convert("RGBA")
                cleaned.putalpha(128)
                return cleaned, "test-rembg", False

            result = process_video_sprite(root, request, source_record(root), make_raw_frames(root), frame_counts=(4,), remover=remover)
            self.assertFalse(result.needs_attention)
            self.assertEqual(set(result.diagnostics), {"test-rembg"})

    def test_cleanup_failure_without_valid_fallback_needs_attention(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            record = source_record(root)
            request = VideoSpriteRequest.from_dict(valid_request(background_mode="rembg", chroma_color=None, frame_counts=[4], output_dir="outputs/fail"))
            result = process_video_sprite(root, request, record, make_raw_frames(root), frame_counts=(4,), remover=lambda image, request: (image, "rembg-failed", True))
            self.assertTrue(result.needs_attention)
            self.assertIn("background-removal-failed", result.attention_reasons)


if __name__ == "__main__":
    unittest.main()
