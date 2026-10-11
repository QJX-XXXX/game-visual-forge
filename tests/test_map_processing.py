from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from tests._bootstrap import ROOT  # noqa: F401
from game_visual_forge.contracts import MapPoint, MapShape, MapShapeType, SourceType
from game_visual_forge.processing.images import ingest_image
from game_visual_forge.processing.map import process_map
from game_visual_forge.quality.map import build_map_asset_manifest, validate_map_outputs
from tests.test_map_contract import make_map_request


class MapProcessingTests(unittest.TestCase):
    def test_process_derives_masks_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "base.png"
            image = Image.new("RGBA", (32, 24), (80, 130, 90, 255))
            ImageDraw.Draw(image).rectangle((0, 0, 31, 23), outline=(20, 60, 30, 255))
            image.save(source)
            request = make_map_request()
            record = ingest_image(root, source, SourceType.EXISTING_FILE, "a" * 64)
            result = process_map(root, request, record, root / request.output_dir)
            staging = root / result.staging_dir

            with Image.open(staging / result.walkable_mask_path) as walkable:
                self.assertEqual(walkable.getpixel((4, 4)), 255)
                self.assertEqual(walkable.getpixel((13, 9)), 0)
            with Image.open(staging / result.collision_mask_path) as collision:
                self.assertEqual(collision.getpixel((0, 0)), 255)
                self.assertEqual(collision.getpixel((4, 4)), 0)

            report = validate_map_outputs(staging, request, record, result)
            self.assertEqual(report.deterministic_status.value, "passed")
            manifest = build_map_asset_manifest(staging, request, record, result, report)
            self.assertEqual(len(manifest.artifacts), 6)
            self.assertEqual(manifest.artifacts[-1].role, "debug-preview")

    def test_spawn_inside_blocker_fails_deterministic_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "base.png"
            Image.new("RGBA", (32, 24), (80, 130, 90, 255)).save(source)
            request = make_map_request()
            request = request.__class__(
                **{**request.__dict__, "spawn": MapPoint(13, 9)}
            )
            record = ingest_image(root, source, SourceType.EXISTING_FILE, "a" * 64)
            result = process_map(root, request, record, root / request.output_dir)
            report = validate_map_outputs(root / result.staging_dir, request, record, result)
            self.assertEqual(report.deterministic_status.value, "failed")


if __name__ == "__main__":
    unittest.main()
