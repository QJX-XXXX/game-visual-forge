from __future__ import annotations

import unittest

from PIL import Image

from tests._bootstrap import ROOT  # noqa: F401
from game_visual_forge.contracts import (
    SourcePreference,
    TileAdjacencyRule,
    TileDefinition,
    TileDirection,
    TileLayer,
    TileMapRequest,
    TileSemanticRole,
)
from game_visual_forge.processing.tilemap_quality import analyze_tilemap_quality


def request_for_tiles(*tiles: TileDefinition, cells: tuple[str | None, ...]) -> TileMapRequest:
    return TileMapRequest(
        1, "quality-fixture", "quality fixture", "outputs/quality-fixture", SourcePreference.EXISTING_FILE,
        16, 16, 2, 1, len(cells), 1, tuple(tiles), (TileLayer("ground", 0, False, cells),),
        "Quality Palette", "Assets/GameVisualForge/quality-fixture",
    )


class TileMapQualityMetricsTests(unittest.TestCase):
    def test_visible_edge_mismatch_sets_needs_attention(self) -> None:
        request = request_for_tiles(TileDefinition("left", 0, 0), TileDefinition("right", 1, 0), cells=("left", "right"))
        atlases = {"page-01": Image.new("RGBA", (32, 16), (0, 0, 0, 0))}
        atlases["page-01"].paste((0, 0, 0, 255), (0, 0, 16, 16))
        atlases["page-01"].paste((255, 255, 255, 255), (16, 0, 32, 16))
        metrics = analyze_tilemap_quality(atlases, request)
        self.assertGreater(metrics.max_seam_score, 48.0)
        self.assertTrue(metrics.needs_attention)

    def test_transparent_decoration_touching_edge_is_reported_as_clipped(self) -> None:
        request = request_for_tiles(TileDefinition("flowers", 0, 0, semantic_role=TileSemanticRole.DECORATION), cells=("flowers", None))
        atlas = Image.new("RGBA", (32, 16), (0, 0, 0, 0))
        atlas.putpixel((0, 8), (255, 0, 0, 255))
        metrics = analyze_tilemap_quality({"page-01": atlas}, request)
        self.assertEqual(metrics.clipped_tile_ids, ("flowers",))

    def test_declared_illegal_neighbor_is_reported(self) -> None:
        request = request_for_tiles(TileDefinition("road-east", 0, 0), TileDefinition("road-west", 1, 0), cells=("road-east", "road-west"))
        request = TileMapRequest(**{**request.__dict__, "adjacency_rules": (TileAdjacencyRule("road-east", TileDirection.EAST, ("road-east",)),)})
        metrics = analyze_tilemap_quality({"page-01": Image.new("RGBA", (32, 16), (0, 0, 0, 255))}, request)
        self.assertEqual(metrics.invalid_adjacencies[0].tile_id, "road-east")


if __name__ == "__main__":
    unittest.main()
