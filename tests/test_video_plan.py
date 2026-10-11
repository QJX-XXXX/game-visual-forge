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

    def test_local_comfyui_h3_plan_optimizes_prompt_and_preserves_job_recovery(self) -> None:
        request = VideoSpriteRequest.from_dict(
            valid_request(
                source_preference="comfyui-h3",
                existing_video_path=None,
                backend="comfy-mcp",
            )
        )
        plan = build_video_execution_plan(request, now="2026-08-09T00:00:00Z")
        actions = [step.action for step in plan.steps]
        self.assertEqual(
            actions,
            [
                "creative-delivery-confirmation",
                "route-video-source",
                "write-minimax-h3-prompt",
                "preflight-comfy-mcp",
                "validate-comfyui-h3-workflow",
                "inspect-comfyui-spend-boundary",
                "run-comfyui-h3-workflow",
                "recover-comfyui-job",
                "fetch-comfyui-video",
                "ingest-local-video",
                "process-local-video-sprite",
                "final-motion-review",
                "validate-video-artifacts",
            ],
        )
        confirmed = [step.action for step in plan.steps if step.requires_confirmation]
        self.assertEqual(confirmed, ["creative-delivery-confirmation", "final-motion-review"])


if __name__ == "__main__":
    unittest.main()
