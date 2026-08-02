from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tests._bootstrap import ROOT  # noqa: F401
from game_visual_forge.contracts import SourceType, TileLayer, TileMapSourceSet, TileAtlasSourceRecord, load_json
from game_visual_forge.processing.images import ingest_image
from game_visual_forge.processing.tilemap import process_tilemap
from game_visual_forge.quality.tilemap import build_tilemap_asset_manifest, validate_tilemap_outputs
from tests.test_tilemap_contract import make_adaptive_tilemap_request, make_tilemap_request


class TileMapProcessingTests(unittest.TestCase):
    def test_process_emits_two_page_unity_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request = make_adaptive_tilemap_request(32)
            request = type(request)(**{**request.__dict__, "layers": (TileLayer("ground", 0, False, ("tile-16", "tile-17", "tile-18", "tile-19")),)})
            records = []
            for page_index in (1, 2):
                source = root / f"page-{page_index:02d}.png"
                atlas = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
                color = (40 * page_index, 100, 60, 255)
                atlas.paste(color, (0, 0, 16, 16))
                atlas.save(source)
                records.append(TileAtlasSourceRecord(f"page-{page_index:02d}", ingest_image(root, source, SourceType.EXISTING_FILE, "a" * 64)))

            result = process_tilemap(root, request, TileMapSourceSet(1, tuple(records)), root / request.output_dir)
            staging = root / result.staging_dir
            slices = load_json(staging / result.slices_path)
            unity = load_json(staging / result.unity_manifest_path)
            self.assertEqual(result.tileset_paths, ("tileset-page-01.png", "tileset-page-02.png"))
            self.assertEqual([page["atlas_id"] for page in slices["atlases"]], ["page-01", "page-02"])
            self.assertEqual(slices["tiles"][16]["atlas_id"], "page-02")
            self.assertEqual(slices["tiles"][16]["palette"], {"x": 4, "y": 3})
            self.assertEqual(unity["tilesets"][1], {"atlas_id": "page-02", "path": "tileset-page-02.png"})
            with Image.open(staging / result.preview_path) as preview:
                self.assertEqual(preview.getpixel((8, 8)), (80, 100, 60, 255))

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
            self.assertEqual([item.role for item in manifest.artifacts[1:]], ["tileset", "sprite-slices", "tilemap-placement", "unity-import-manifest", "tilemap-preview", "tilemap-quality-metrics", "tile-seam-preview", "tile-usage-preview"])

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
