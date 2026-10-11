from __future__ import annotations

import unittest

from PIL import Image

from tests._bootstrap import ROOT  # noqa: F401
from game_visual_forge.contracts import (
    BridgeConnectivityRule,
    BridgeOrientation,
    SourcePreference,
    TileAdjacencyRule,
    TileDefinition,
    TileDirection,
    TileLayer,
    TileMapRequest,
    TileSemanticRole,
)
from game_visual_forge.processing.tilemap_quality import analyze_tilemap_quality, render_seam_preview, seam_samples


def request_for_tiles(*tiles: TileDefinition, cells: tuple[str | None, ...]) -> TileMapRequest:
    return TileMapRequest(
        1, "quality-fixture", "quality fixture", "outputs/quality-fixture", SourcePreference.EXISTING_FILE,
        16, 16, 2, 1, len(cells), 1, tuple(tiles), (TileLayer("ground", 0, False, cells),),
        "Quality Palette", "Assets/GameVisualForge/quality-fixture",
    )


def bridge_request(
    width: int,
    height: int,
    cells: tuple[str | None, ...],
    rule: BridgeConnectivityRule,
    approach_cells: tuple[str | None, ...] | None = None,
) -> TileMapRequest:
    tiles = (
        TileDefinition("road-custom", 0, 0, semantic_role=TileSemanticRole.ROAD),
        TileDefinition("bridge-custom", 1, 0, semantic_role=TileSemanticRole.BRIDGE),
        TileDefinition("water-custom", 2, 0, semantic_role=TileSemanticRole.WATER),
        TileDefinition("terrain-custom", 3, 0, semantic_role=TileSemanticRole.TERRAIN),
    )
    layers = [TileLayer("ground", 0, False, cells)]
    if approach_cells is not None:
        layers.append(TileLayer("approach", 1, False, approach_cells))
    return TileMapRequest(
        1, "bridge-quality-fixture", "bridge quality fixture", "outputs/bridge-quality-fixture", SourcePreference.EXISTING_FILE,
        16, 16, 4, 1, width, height, tiles, tuple(layers), "Quality Palette", "Assets/GameVisualForge/bridge-quality-fixture",
        bridge_connectivity_rules=(rule,),
    )


def bridge_atlas() -> dict[str, Image.Image]:
    atlas = Image.new("RGBA", (64, 16), (0, 0, 0, 255))
    for index, color in enumerate(((70, 140, 70, 255), (130, 80, 30, 255), (20, 80, 180, 255), (90, 90, 90, 255))):
        atlas.paste(color, (index * 16, 0, (index + 1) * 16, 16))
    return {"page-01": atlas}


class TileMapQualityMetricsTests(unittest.TestCase):
    def test_complete_horizontal_and_vertical_bridges_pass(self) -> None:
        horizontal = bridge_request(
            4, 1,
            ("road-custom", "bridge-custom", "bridge-custom", "road-custom"),
            BridgeConnectivityRule("horizontal", BridgeOrientation.HORIZONTAL, "ground", 1, 0, 2, 0),
        )
        vertical = bridge_request(
            1, 4,
            ("road-custom", "bridge-custom", "bridge-custom", "road-custom"),
            BridgeConnectivityRule("vertical", BridgeOrientation.VERTICAL, "ground", 0, 1, 0, 2),
        )
        self.assertEqual(analyze_tilemap_quality(bridge_atlas(), horizontal).invalid_bridge_connectivity, ())
        self.assertEqual(analyze_tilemap_quality(bridge_atlas(), vertical).invalid_bridge_connectivity, ())

    def test_bridge_failures_report_rule_layer_coordinates_and_semantics(self) -> None:
        request = bridge_request(
            4, 1,
            ("road-custom", "bridge-custom", "water-custom", "terrain-custom"),
            BridgeConnectivityRule("river-crossing", BridgeOrientation.HORIZONTAL, "ground", 1, 0, 2, 0),
        )
        metrics = analyze_tilemap_quality(bridge_atlas(), request)
        failures = metrics.invalid_bridge_connectivity
        self.assertEqual([(item.x, item.y, item.expected_role, item.actual_tile_id, item.actual_role) for item in failures], [
            (2, 0, "bridge", "water-custom", "water"),
            (3, 0, "road", "terrain-custom", "terrain"),
        ])
        self.assertEqual(failures[0].rule_id, "river-crossing")
        self.assertEqual(failures[0].layer_id, "ground")
        self.assertTrue(metrics.needs_attention)

    def test_cross_layer_approaches_and_single_cell_bridge_pass(self) -> None:
        request = bridge_request(
            3, 1,
            ("terrain-custom", "bridge-custom", "terrain-custom"),
            BridgeConnectivityRule("single", BridgeOrientation.HORIZONTAL, "ground", 1, 0, 1, 0, "approach"),
            ("road-custom", None, "road-custom"),
        )
        self.assertEqual(analyze_tilemap_quality(bridge_atlas(), request).invalid_bridge_connectivity, ())
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

    def test_seam_preview_is_distinct_even_when_all_seams_pass(self) -> None:
        request = request_for_tiles(TileDefinition("grass", 0, 0), cells=("grass", "grass"))
        atlas = Image.new("RGBA", (16, 16), (40, 80, 40, 255))
        preview = Image.new("RGBA", (32, 16), (40, 80, 40, 255))
        samples = seam_samples({"page-01": atlas}, request)
        rendered = render_seam_preview(preview, samples, request)
        self.assertNotEqual(rendered.tobytes(), preview.tobytes())


if __name__ == "__main__":
    unittest.main()
