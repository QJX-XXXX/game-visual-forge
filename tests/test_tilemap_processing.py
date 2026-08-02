from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tests._bootstrap import ROOT  # noqa: F401
from game_visual_forge.contracts import SourceType, load_json
from game_visual_forge.processing.images import ingest_image
from game_visual_forge.processing.tilemap import process_tilemap
from game_visual_forge.quality.tilemap import build_tilemap_asset_manifest, validate_tilemap_outputs
from tests.test_tilemap_contract import make_tilemap_request


class TileMapProcessingTests(unittest.TestCase):
    def test_process_emits_unity_bundle_and_preview(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "tileset.png"
            atlas = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
            colors = ((45, 140, 65, 255), (100, 100, 100, 255), (35, 90, 180, 255), (220, 100, 180, 255))
            for index, color in enumerate(colors):
                x = (index % 2) * 16
                y = (index // 2) * 16
                atlas.paste(color, (x, y, x + 16, y + 16))
            atlas.save(source)

            request = make_tilemap_request()
            record = ingest_image(root, source, SourceType.EXISTING_FILE, "a" * 64)
            result = process_tilemap(root, request, record, root / request.output_dir)
            staging = root / result.staging_dir

            slices = load_json(staging / result.slices_path)
            self.assertEqual(slices["tiles"][0]["rect"], {"x": 0, "y": 16, "width": 16, "height": 16})
            placement = load_json(staging / result.placement_path)
            self.assertEqual(placement["layers"][0]["placements"][0], {"x": 0, "y": 1, "tile_id": "grass"})
            with Image.open(staging / result.preview_path) as preview:
                self.assertEqual(preview.size, (48, 32))
                self.assertEqual(preview.getpixel((8, 8)), colors[0])
                self.assertEqual(preview.getpixel((24, 8)), colors[3])

            report = validate_tilemap_outputs(staging, request, record, result)
            self.assertEqual(report.deterministic_status.value, "passed")
            manifest = build_tilemap_asset_manifest(staging, request, record, result, report)
            self.assertEqual([item.role for item in manifest.artifacts[1:]], ["tileset", "sprite-slices", "tilemap-placement", "unity-import-manifest", "tilemap-preview"])

    def test_incorrect_atlas_size_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "tileset.png"
            Image.new("RGBA", (31, 32), (0, 0, 0, 0)).save(source)
            request = make_tilemap_request()
            record = ingest_image(root, source, SourceType.EXISTING_FILE, "a" * 64)
            with self.assertRaisesRegex(Exception, "tileset dimensions"):
                process_tilemap(root, request, record, root / request.output_dir)


if __name__ == "__main__":
    unittest.main()
