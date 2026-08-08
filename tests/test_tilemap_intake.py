from __future__ import annotations

import unittest

from tests._bootstrap import ROOT  # noqa: F401
from tests.tilemap_workflow_fixtures import build_workflow_request_payload
from game_visual_forge.contracts import TileMapIntakeStatus, assess_tilemap_intake


class TileMapIntakeTests(unittest.TestCase):
    def test_missing_fields_are_grouped_once_in_stable_order(self) -> None:
        payload = build_workflow_request_payload(intake_overrides={"art_style": "", "mood": "", "scene_path": ""})
        assessment = assess_tilemap_intake(payload)
        self.assertEqual(assessment.status, TileMapIntakeStatus.NEEDS_USER_INPUT)
        self.assertEqual([item.question_group_id for item in assessment.question_groups], ["visual", "delivery"])

    def test_complete_unconfirmed_intake_returns_one_summary(self) -> None:
        assessment = assess_tilemap_intake(build_workflow_request_payload())
        self.assertEqual(assessment.status, TileMapIntakeStatus.NEEDS_USER_CONFIRMATION)
        self.assertIn("Player", assessment.confirmation_summary)
        self.assertEqual(len(assessment.confirmation_sha256), 64)

    def test_changed_intake_invalidates_confirmation_hash(self) -> None:
        payload = build_workflow_request_payload()
        first = assess_tilemap_intake(payload)
        payload["intake"].update(requirements_confirmed=True, confirmed_summary_sha256=first.confirmation_sha256)
        self.assertEqual(assess_tilemap_intake(payload).status, TileMapIntakeStatus.CONFIRMED)
        payload["intake"]["art_style"] = "hand-painted"
        self.assertEqual(assess_tilemap_intake(payload).status, TileMapIntakeStatus.NEEDS_USER_CONFIRMATION)

    def test_request_round_trips_optional_intake_and_legacy_payload(self) -> None:
        from game_visual_forge.contracts import TileMapRequest

        payload = build_workflow_request_payload()
        request = TileMapRequest.from_dict(payload)
        self.assertEqual(TileMapRequest.from_dict(request.to_dict()), request)
        payload.pop("intake")
        self.assertIsNone(TileMapRequest.from_dict(payload).intake)


if __name__ == "__main__":
    unittest.main()
