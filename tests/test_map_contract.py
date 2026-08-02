from __future__ import annotations

import unittest

from tests._bootstrap import ROOT  # noqa: F401
from game_visual_forge.contracts import (
    MapPoint,
    MapRequest,
    MapShape,
    MapShapeType,
    SourcePreference,
)


def make_map_request() -> MapRequest:
    return MapRequest(
        schema_version=1,
        asset_id="shrine-map",
        prompt="A clean HD shrine courtyard.",
        output_dir="outputs/shrine-map",
        source_preference=SourcePreference.EXISTING_FILE,
        canvas_width=32,
        canvas_height=24,
        spawn=MapPoint(4, 4),
        walk_bounds=(MapShape("courtyard", MapShapeType.RECT, x=2, y=2, width=28, height=20),),
        blockers=(MapShape("shrine", MapShapeType.RECT, x=12, y=8, width=6, height=6),),
        zones=(MapShape("rest", MapShapeType.CIRCLE, x=5, y=5, radius=3),),
    )


class MapContractTests(unittest.TestCase):
    def test_request_round_trip_is_exact(self) -> None:
        request = make_map_request()
        self.assertEqual(MapRequest.from_dict(request.to_dict()), request)

    def test_shape_bounds_are_checked_against_canvas(self) -> None:
        with self.assertRaisesRegex(ValueError, "outside the map canvas"):
            MapRequest(
                schema_version=1,
                asset_id="bad-map",
                prompt="bad",
                output_dir="outputs/bad-map",
                source_preference=SourcePreference.EXISTING_FILE,
                canvas_width=32,
                canvas_height=24,
                spawn=MapPoint(1, 1),
                walk_bounds=(MapShape("outside", MapShapeType.RECT, x=20, y=2, width=20, height=4),),
            )

    def test_polygon_requires_three_points(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least three"):
            MapShape("triangle", MapShapeType.POLYGON, points=(MapPoint(1, 1), MapPoint(2, 2)))


if __name__ == "__main__":
    unittest.main()
