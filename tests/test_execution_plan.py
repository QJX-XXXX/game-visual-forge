from __future__ import annotations

import unittest

from tests._bootstrap import ROOT  # noqa: F401
from game_visual_forge.cli.planning import build_execution_plan
from game_visual_forge.contracts import AssetBrief, AssetKind, SourcePreference


def brief(source: SourcePreference) -> AssetBrief:
    return AssetBrief(
        1,
        "hero-run",
        AssetKind.SPRITE,
        "A running hero.",
        "outputs/hero-run",
        source,
        frame_count=8,
    )


class ExecutionPlanTests(unittest.TestCase):
    def test_auto_source_starts_with_agent_native_capability_check(self) -> None:
        plan = build_execution_plan(brief(SourcePreference.AUTO))
        self.assertEqual(plan.steps[0].action, "check-agent-native")
        self.assertFalse(plan.steps[0].requires_confirmation)
        self.assertEqual(plan.steps[1].action, "generate-agent-native")

    def test_explicit_third_party_requires_provider_and_paid_confirmation(self) -> None:
        plan = build_execution_plan(brief(SourcePreference.JIMENG))
        actions = [step.action for step in plan.steps]
        self.assertEqual(
            actions[:3],
            [
                "preflight-provider",
                "confirm-paid-submit",
                "generate-provider-media",
            ],
        )
        self.assertTrue(plan.steps[1].requires_confirmation)

    def test_plan_has_no_network_execution_flag(self) -> None:
        plan = build_execution_plan(brief(SourcePreference.WANXIANG))
        self.assertTrue(plan.dry_run)


if __name__ == "__main__":
    unittest.main()
