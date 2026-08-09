from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests._bootstrap import ROOT

from game_visual_forge.contracts.video import VideoBackgroundMode, VideoSpriteRequest
from game_visual_forge.contracts.video import VideoSourceRecord
from game_visual_forge.processing.video_frames import build_sampling_plan
from game_visual_forge.processing.video_probe import sha256_file
from game_visual_forge.processing.video_sprite import process_video_sprite
from tests.test_video_contract import valid_request


def source_record(root: Path) -> VideoSourceRecord:
    source = root / "source.mp4"
    source.write_bytes(b"video")
    return VideoSourceRecord(1, "source.mp4", sha256_file(source), "mp4", "h264", 64, 64, 0, 1.0, "24/1", "24/1", False, 24, False, "a" * 64)


def make_raw_frames(root: Path, count: int = 4):
    from PIL import Image
    raw = root / "raw"
    raw.mkdir()
    records = []
    for index in range(count):
        image = Image.new("RGBA", (32, 32), (255, 0, 255, 255))
        for x in range(4 + index, 12 + index):
            for y in range(10, 26):
                image.putpixel((x, y), (255, 255, 255, 255))
        path = raw / f"frame-{index:04d}.png"
        image.save(path)
        from game_visual_forge.contracts.video import VideoFrameRecord
        records.append(VideoFrameRecord(1, index, index / count, None, path.relative_to(root).as_posix(), None, None, sha256_file(path)))
    return tuple(records)


class VideoProcessingTests(unittest.TestCase):
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
            self.assertEqual(Image.open(delivery).size, (64, 64))
            self.assertEqual(Image.open(delivery).getpixel((0, 0))[3], 0)

    def test_pixel_mode_uses_one_canvas_for_every_frame(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            record = source_record(root)
            request = VideoSpriteRequest.from_dict(valid_request(background_mode="preserve", processing_mode="pixel", frame_counts=[4], canvas_width=48, canvas_height=48, output_dir="outputs/pixel"))
            result = process_video_sprite(root, request, record, make_raw_frames(root), frame_counts=(4,))
            from PIL import Image
            paths = [root / result.artifacts["frames:4"] / f"frame-{index:03d}.png" for index in range(4)]
            self.assertEqual({Image.open(path).size for path in paths}, {(48, 48)})

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
