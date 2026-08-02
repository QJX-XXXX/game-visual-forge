from __future__ import annotations

import unittest

from tests._bootstrap import ROOT  # noqa: F401
from game_visual_forge.contracts import SourcePreference, TileColliderType, TileDefinition, TileLayer, TileMapRequest


def make_tilemap_request() -> TileMapRequest:
    return TileMapRequest(
        schema_version=1,
        asset_id="forest-tiles",
        prompt="A coherent pixel-art forest tileset with grass, stone, and water.",
        output_dir="outputs/forest-tiles",
        source_preference=SourcePreference.EXISTING_FILE,
        tile_width=16,
        tile_height=16,
        atlas_columns=2,
        atlas_rows=2,
        map_width=3,
        map_height=2,
        pixels_per_unit=16,
        palette_name="Forest Palette",
        unity_generated_root="Assets/GameVisualForge/forest-tiles",
        tiles=(
            TileDefinition("grass", 0, 0),
            TileDefinition("stone", 1, 0, TileColliderType.GRID),
            TileDefinition("water", 0, 1, TileColliderType.SPRITE),
            TileDefinition("flowers", 1, 1),
        ),
        layers=(
            TileLayer("ground", 0, False, ("grass", "grass", "water", "stone", "grass", "water")),
            TileLayer("details", 1, True, (None, "flowers", None, None, None, None)),
        ),
    )


class TileMapContractTests(unittest.TestCase):
    def test_request_round_trip_is_exact(self) -> None:
        request = make_tilemap_request()
        self.assertEqual(TileMapRequest.from_dict(request.to_dict()), request)
        self.assertEqual(request.expected_atlas_size, (32, 32))

    def test_unknown_tile_reference_is_rejected(self) -> None:
        request = make_tilemap_request()
        with self.assertRaisesRegex(ValueError, "unknown tiles"):
            TileMapRequest(**{**request.__dict__, "layers": (TileLayer("bad", 0, False, ("missing", None, None, None, None, None)),)})

    def test_duplicate_atlas_cell_is_rejected(self) -> None:
        request = make_tilemap_request()
        with self.assertRaisesRegex(ValueError, "atlas cells"):
            TileMapRequest(**{**request.__dict__, "tiles": (*request.tiles, TileDefinition("duplicate", 0, 0))})


if __name__ == "__main__":
    unittest.main()
