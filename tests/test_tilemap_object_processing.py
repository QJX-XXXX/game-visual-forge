from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tests.test_tilemap_contract import make_tilemap_request
from game_visual_forge.contracts import (
    GridCell, GridRect, RawImageRecord, SourceType, TileMapSourceSet, TileObjectAssetDefinition,
    TileObjectKind, TileObjectPlacement, TileObjectEntrance, EntranceConnectionTarget, TileMapRequest,
    TileAtlasSourceRecord, TileObjectSourceRecord,
)
from game_visual_forge.processing.tilemap import process_tilemap


def record(path: Path, fingerprint: str) -> RawImageRecord:
    return RawImageRecord(1, path.relative_to(path.parents[1]).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest(), *Image.open(path).size, "png", SourceType.EXISTING_FILE, fingerprint)


class TileMapObjectProcessingTests(unittest.TestCase):
    def test_process_emits_runtime_object_and_collision_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            atlas_path = root / "atlas.png"
            object_path = root / "inn.png"
            Image.new("RGBA", (32, 32), (80, 180, 80, 255)).save(atlas_path)
            object_image = Image.new("RGBA", (32, 32), (180, 80, 40, 255))
            object_image.putpixel((0, 0), (0, 0, 0, 0))
            object_image.save(object_path)
            fp = "a" * 64
            request = make_tilemap_request()
            asset = TileObjectAssetDefinition("inn", TileObjectKind.BUILDING, "inn", 32, 32, 16, 0, 0, GridRect(0, 0, 2, 2), (GridCell(0, 1),), GridCell(1, 1), 1, 0)
            request = TileMapRequest(**{**request.__dict__, "object_assets": (asset,), "object_placements": (TileObjectPlacement("inn-1", "inn", 0, 0, 10),), "object_entrances": (TileObjectEntrance("entry", "inn-1", EntranceConnectionTarget.WALKABLE, "interiors/inn", "entry"),), "gameplay_crop": GridRect(0, 0, 2, 2)})
            atlas = RawImageRecord(1, "atlas.png", hashlib.sha256(atlas_path.read_bytes()).hexdigest(), 32, 32, "png", SourceType.EXISTING_FILE, fp)
            obj = RawImageRecord(1, "inn.png", hashlib.sha256(object_path.read_bytes()).hexdigest(), 32, 32, "png", SourceType.EXISTING_FILE, fp)
            source = TileMapSourceSet(1, (TileAtlasSourceRecord("page-01", atlas),), (TileObjectSourceRecord("inn", obj),))
            result = process_tilemap(root, request, source, root / "outputs" / "village")
            staging = root / result.staging_dir
            self.assertEqual(result.objects_path, "tilemap-objects.json")
            self.assertEqual(result.collision_path, "tilemap-collision.json")
            self.assertTrue((staging / "objects" / "inn.png").exists())
            self.assertTrue((staging / result.gameplay_crop_path).exists())
            self.assertTrue((staging / result.collision_preview_path).exists())


if __name__ == "__main__":
    unittest.main()
