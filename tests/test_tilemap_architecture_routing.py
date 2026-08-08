from __future__ import annotations

import unittest

from tests._bootstrap import ROOT  # noqa: F401
from tests.tilemap_workflow_fixtures import build_workflow_request_payload
from game_visual_forge.contracts import LayoutStrategy, TileMapRequest, TileSetProfile, tilemap_confirmation_sha256
from game_visual_forge.jobs import fingerprint_request
from game_visual_forge.routing import select_tilemap_architecture


class TileMapArchitectureRoutingTests(unittest.TestCase):
    def confirmed_request(self, **changes) -> TileMapRequest:
        payload = build_workflow_request_payload()
        request = TileMapRequest.from_dict(payload)
        digest = fingerprint_request(request.to_dict())
        intake = request.intake
        assert intake is not None
        from dataclasses import replace
        intake = replace(intake, requirements_confirmed=True, confirmed_summary_sha256=None)
        from game_visual_forge.contracts import tilemap_confirmation_sha256
        intake_changes = changes.pop("intake", {})
        if intake_changes:
            intake = replace(intake, **intake_changes)
        intake = replace(intake, confirmed_summary_sha256=tilemap_confirmation_sha256(intake))
        return TileMapRequest(**{**request.__dict__, "intake": intake, **changes})

    def test_fixed_continuity_map_selects_coherent_foundation(self) -> None:
        request = self.confirmed_request()
        decision = select_tilemap_architecture(request, fingerprint_request(request.to_dict()))
        self.assertEqual(decision.selected_profile, TileSetProfile.COHERENT_FOUNDATION)
        self.assertTrue(decision.requires_complete_foundation)

    def test_reusable_map_selects_demand_driven(self) -> None:
        from dataclasses import replace
        base = self.confirmed_request()
        intake = replace(base.intake, layout_strategy=LayoutStrategy.REUSABLE, continuity_features=())
        intake = replace(intake, confirmed_summary_sha256=tilemap_confirmation_sha256(intake))
        request = TileMapRequest(**{**base.__dict__, "intake": intake})
        request = TileMapRequest(**{**request.__dict__, "tileset_profile": TileSetProfile.DEMAND_DRIVEN})
        decision = select_tilemap_architecture(request, fingerprint_request(request.to_dict()))
        self.assertEqual(decision.selected_profile, TileSetProfile.DEMAND_DRIVEN)

    def test_profile_conflict_blocks_plan(self) -> None:
        request = self.confirmed_request(tileset_profile=TileSetProfile.DEMAND_DRIVEN)
        with self.assertRaisesRegex(ValueError, "architecture requires coherent_foundation"):
            select_tilemap_architecture(request, fingerprint_request(request.to_dict()))


if __name__ == "__main__":
    unittest.main()
