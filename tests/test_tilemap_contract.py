from __future__ import annotations

import unittest

from tests._bootstrap import ROOT  # noqa: F401
from game_visual_forge.contracts import (
    AtlasPageDefinition,
    SourcePreference,
    TileColliderType,
    TileDefinition,
    TileLayer,
    TileMapRequest,
    TileSizeMode,
    TileSetProfile,
)


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


def make_adaptive_tilemap_request(tile_count: int = 32) -> TileMapRequest:
    pages = tuple(
        AtlasPageDefinition(f"page-{index:02d}", 4, 4, 16, 16, f"Page {index} forest terrain")
        for index in range(1, (tile_count + 15) // 16 + 1)
    )
    tiles = tuple(
        TileDefinition(
            f"tile-{index:02d}",
            index % 4,
            (index // 4) % 4,
            atlas_id=pages[index // 16].atlas_id,
        )
        for index in range(tile_count)
    )
    return TileMapRequest(
        schema_version=1,
        asset_id="adaptive-forest",
        prompt="A high quality adaptive forest tileset.",
        output_dir="outputs/adaptive-forest",
        source_preference=SourcePreference.EXISTING_FILE,
        tile_width=16,
        tile_height=16,
        atlas_columns=4,
        atlas_rows=4,
        map_width=2,
        map_height=2,
        palette_name="Adaptive Forest Palette",
        unity_generated_root="Assets/GameVisualForge/adaptive-forest",
        tiles=tiles,
        layers=(TileLayer("ground", 0, False, ("tile-00", "tile-01", "tile-02", "tile-03")),),
        tileset_profile=TileSetProfile.ADAPTIVE_HD,
        max_tile_count=tile_count if tile_count in {16, 32, 48} else 48,
        atlas_pages=pages,
    )


class TileMapContractTests(unittest.TestCase):
    def test_tile_size_mode_is_inferred_for_legacy_requests(self) -> None:
        request_16 = make_tilemap_request()
        request_32 = TileMapRequest(**{**request_16.__dict__, "tile_width": 32, "tile_height": 32, "pixels_per_unit": 32, "tile_size_mode": None})
        rectangular = TileMapRequest(**{**request_16.__dict__, "tile_height": 18, "tile_size_mode": None})

        self.assertIs(request_16.tile_size_mode, TileSizeMode.PRESET_16)
        self.assertIs(request_32.tile_size_mode, TileSizeMode.PRESET_32)
        self.assertIs(rectangular.tile_size_mode, TileSizeMode.CUSTOM)

    def test_explicit_preset_conflicts_are_rejected(self) -> None:
        request = make_tilemap_request()

        with self.assertRaisesRegex(ValueError, "preset_32"):
            TileMapRequest(**{**request.__dict__, "tile_size_mode": TileSizeMode.PRESET_32})

    def test_atlas_page_dimension_mismatch_is_rejected(self) -> None:
        request = make_adaptive_tilemap_request()
        mismatched_page = AtlasPageDefinition("page-02", 4, 4, 16, 18, "Second page")

        with self.assertRaisesRegex(ValueError, "tile dimensions"):
            TileMapRequest(**{**request.__dict__, "atlas_pages": (request.atlas_pages[0], mismatched_page)})

    def test_tile_size_mode_round_trips_and_legacy_payloads_parse(self) -> None:
        request = make_tilemap_request()
        payload = request.to_dict()

        self.assertEqual(payload["tile_size_mode"], "preset_16")
        self.assertEqual(TileMapRequest.from_dict(payload), request)
        payload.pop("tile_size_mode")
        self.assertEqual(TileMapRequest.from_dict(payload).tile_size_mode, TileSizeMode.PRESET_16)

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

    def test_adaptive_request_round_trips_three_pages(self) -> None:
        request = make_adaptive_tilemap_request(40)
        self.assertEqual(request.tileset_profile, TileSetProfile.ADAPTIVE_HD)
        self.assertEqual(len(request.resolved_atlas_pages), 3)
        self.assertEqual(request.expected_atlas_sizes["page-03"], (64, 64))
        self.assertEqual(TileMapRequest.from_dict(request.to_dict()), request)

    def test_same_local_cell_is_allowed_on_different_pages(self) -> None:
        request = make_adaptive_tilemap_request(16)
        duplicate_page_cell = TileDefinition("page-two-origin", 0, 0, atlas_id="page-02")
        updated = TileMapRequest(
            **{
                **request.__dict__,
                "tiles": (*request.tiles, duplicate_page_cell),
                "max_tile_count": 32,
                "atlas_pages": (*request.atlas_pages, AtlasPageDefinition("page-02", 4, 4, 16, 16, "Second page")),
            }
        )
        self.assertEqual(updated.tiles[-1].atlas_id, "page-02")

    def test_legacy_single_page_request_remains_valid(self) -> None:
        request = make_tilemap_request()
        self.assertEqual(request.resolved_atlas_pages[0].atlas_id, "page-01")
        self.assertEqual(request.expected_atlas_sizes, {"page-01": (32, 32)})


if __name__ == "__main__":
    unittest.main()
