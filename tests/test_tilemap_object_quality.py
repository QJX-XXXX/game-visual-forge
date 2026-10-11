from __future__ import annotations

import unittest
from PIL import Image

from tests.test_tilemap_contract import make_tilemap_request
from game_visual_forge.contracts import GridCell, GridRect, TileMapRequest, TileObjectAssetDefinition, TileObjectKind
from game_visual_forge.quality.tilemap_objects import analyze_object_quality


class TileMapObjectQualityTests(unittest.TestCase):
    def test_duplicate_buildings_are_rejected(self) -> None:
        base = make_tilemap_request()
        asset_a = TileObjectAssetDefinition("inn", TileObjectKind.BUILDING, "inn", 16, 16, 16, 0, 0, GridRect(0, 0, 1, 1), (), GridCell(0, 0), 2, 0)
        asset_b = TileObjectAssetDefinition("shop", TileObjectKind.BUILDING, "shop", 16, 16, 16, 0, 0, GridRect(0, 0, 1, 1), (), GridCell(0, 0), 2, 0)
        request = TileMapRequest(**{**base.__dict__, "object_assets": (asset_a, asset_b)})
        image = Image.new("RGBA", (16, 16), (180, 80, 40, 255))
        metrics = analyze_object_quality(request, {"inn": image, "shop": image.copy()})
        self.assertTrue(any(item.startswith("duplicate:") for item in metrics.silhouette_failures))


if __name__ == "__main__":
    unittest.main()
