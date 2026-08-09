from __future__ import annotations

import unittest

from tests._bootstrap import ROOT

from game_visual_forge.cli.planning import build_video_execution_plan
from game_visual_forge.contracts.video import VideoSpriteRequest
from tests.test_video_contract import valid_request


class VideoPlanTests(unittest.TestCase):
    def test_existing_video_plan_has_no_paid_step(self) -> None:
        plan = build_video_execution_plan(VideoSpriteRequest.from_dict(valid_request()), now="2026-08-09T00:00:00Z")
        actions = [step.action for step in plan.steps]
        self.assertNotIn("paid-submit-confirmation", actions)
        self.assertEqual(actions[-1], "validate-video-artifacts")

    def test_generated_video_plan_contains_three_gates(self) -> None:
        request = VideoSpriteRequest.from_dict(valid_request(source_preference="minimax", existing_video_path=None, backend="api"))
        plan = build_video_execution_plan(request, now="2026-08-09T00:00:00Z")
        confirmed = [step.action for step in plan.steps if step.requires_confirmation]
        self.assertEqual(confirmed, ["creative-delivery-confirmation", "paid-submit-confirmation", "final-motion-review"])


if __name__ == "__main__":
    unittest.main()
