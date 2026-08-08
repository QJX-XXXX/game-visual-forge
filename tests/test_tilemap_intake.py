from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
import json

from tests._bootstrap import ROOT  # noqa: F401
from tests.tilemap_workflow_fixtures import build_workflow_request_payload
from game_visual_forge.contracts import TileMapIntakeStatus, assess_tilemap_intake


class TileMapIntakeTests(unittest.TestCase):
    def test_plan_writes_nothing_before_intake_confirmation(self) -> None:
        from game_visual_forge.cli.tilemap import run_tilemap_plan

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request_path = root / "request.json"
            out_dir = root / "run"
            request_path.write_text(json.dumps(build_workflow_request_payload()), encoding="utf-8")
            result = run_tilemap_plan(request_path, out_dir, "2026-08-08T00:00:00Z")
            self.assertEqual(result["status"], "needs_user_confirmation")
            self.assertFalse((out_dir / "execution-plan.json").exists())
            self.assertFalse((out_dir / "job-state.json").exists())

    def test_legacy_plan_remains_compatible(self) -> None:
        from game_visual_forge.cli.tilemap import run_tilemap_plan
        from tests.test_tilemap_contract import make_tilemap_request

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request_path = root / "request.json"
            out_dir = root / "run"
            request_path.write_text(json.dumps(make_tilemap_request().to_dict()), encoding="utf-8")
            result = run_tilemap_plan(request_path, out_dir, "2026-08-08T00:00:00Z")
            self.assertEqual(result["status"], "planned")
            self.assertTrue((out_dir / "execution-plan.json").exists())
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
