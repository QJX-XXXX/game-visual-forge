from __future__ import annotations

import unittest

from tests.test_tilemap_contract import make_tilemap_request
from game_visual_forge.contracts import (
    EntranceConnectionTarget,
    GridCell,
    GridRect,
    RoadConnectivityPolicy,
    TileMapApprovalWorkflow,
    TileMapRequest,
    TileObjectAssetDefinition,
    TileObjectEntrance,
    TileObjectKind,
    TileObjectPlacement,
)


class TileMapObjectContractTests(unittest.TestCase):
    def test_object_assets_and_entrances_round_trip(self) -> None:
        asset = TileObjectAssetDefinition(
            "inn", TileObjectKind.BUILDING, "warm inn", 192, 160, 32, 3, 4,
            GridRect(0, 0, 6, 5), tuple(GridCell(x, y) for y in range(5) for x in range(6) if (x, y) != (3, 4)), GridCell(3, 4), 1, 0,
        )
        placement = TileObjectPlacement("inn-instance", "inn", 0, 0, 100)
        entrance = TileObjectEntrance("inn-entrance", "inn-instance", EntranceConnectionTarget.ROAD, "interiors/inn", "entry")
        self.assertEqual(TileObjectAssetDefinition.from_dict(asset.to_dict()), asset)
        self.assertEqual(TileObjectPlacement.from_dict(placement.to_dict()), placement)
        self.assertEqual(TileObjectEntrance.from_dict(entrance.to_dict()), entrance)

    def test_building_doorway_must_be_clear(self) -> None:
        with self.assertRaisesRegex(ValueError, "doorway_cell"):
            TileObjectAssetDefinition("inn", TileObjectKind.BUILDING, "inn", 64, 64, 32, 0, 0, GridRect(0, 0, 2, 2), (GridCell(0, 0),), GridCell(0, 0), 1, 0)

    def test_road_policy_requires_only_declared_data(self) -> None:
        self.assertEqual(TileMapRequest(**{**make_tilemap_request().__dict__, "road_connectivity_policy": RoadConnectivityPolicy.NONE}).road_connection_requirements, ())
        with self.assertRaisesRegex(ValueError, "partial"):
            TileMapRequest(**{**make_tilemap_request().__dict__, "road_connectivity_policy": RoadConnectivityPolicy.PARTIAL, "road_connection_requirements": ()})

    def test_two_gate_requires_crop_and_object_buildings(self) -> None:
        with self.assertRaisesRegex(ValueError, "gameplay_crop"):
            TileMapRequest(**{**make_tilemap_request().__dict__, "approval_workflow": TileMapApprovalWorkflow.TWO_GATE})


if __name__ == "__main__":
    unittest.main()
