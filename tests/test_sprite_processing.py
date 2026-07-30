from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from tests._bootstrap import ROOT  # noqa: F401
from game_visual_forge.contracts import BackgroundRemoval, SpriteOutput
from game_visual_forge.processing.background import remove_chroma, remove_background
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

    def test_missing_rembg_preserves_background_with_attention_flag(self) -> None:
        request = replace(self.request(), background_removal=BackgroundRemoval.REMBG, chroma_color=None)
        with patch("game_visual_forge.processing.background._load_rembg", return_value=None):
            result = remove_background(Image.new("RGBA", (2, 2), (1, 2, 3, 255)), request)
        self.assertEqual(result.method, "preserve-background")
        self.assertTrue(result.needs_attention)


def request_source_type(request):
    from game_visual_forge.contracts import SourceType
    return SourceType.EXISTING_FILE


if __name__ == "__main__":
    unittest.main()
