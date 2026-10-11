from __future__ import annotations

import unittest

from tests._bootstrap import ROOT  # noqa: F401
from game_visual_forge.cli.planning import build_execution_plan
from game_visual_forge.contracts import ExecutionPlan, PlanStep
from game_visual_forge.contracts import (
    AssetBrief,
    AssetKind,
    AtlasPageDefinition,
    SourcePreference,
    TileDefinition,
    TileLayer,
    TileMapRequest,
    TileSetProfile,
)


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
    def adaptive_tilemap_request(self) -> TileMapRequest:
        return TileMapRequest(
            1,
            "adaptive-plan",
            "Adaptive forest tileset",
            "outputs/adaptive-plan",
            SourcePreference.EXISTING_FILE,
            16,
            16,
            4,
            4,
            1,
            1,
            (TileDefinition("grass", 0, 0),),
            (TileLayer("ground", 0, False, ("grass",)),),
            "Adaptive Palette",
            "Assets/GameVisualForge/adaptive-plan",
            tileset_profile=TileSetProfile.ADAPTIVE_HD,
            atlas_pages=(AtlasPageDefinition("page-01", 4, 4, 16, 16, "grass"),),
        )

    def test_adaptive_tilemap_plan_obtains_pages(self) -> None:
        from game_visual_forge.cli.planning import build_tilemap_execution_plan

        actions = [step.action for step in build_tilemap_execution_plan(self.adaptive_tilemap_request()).steps]
        self.assertIn("obtain-local-tileset-pages", actions)

    def make_step(
        self,
        *,
        step_id: str = "step-01",
        depends_on: tuple[str, ...] = (),
        requires_confirmation: bool = False,
    ) -> PlanStep:
        return PlanStep(
            step_id=step_id,
            action="generate-agent-native",
            owner="agent",
            depends_on=depends_on,
            requires_confirmation=requires_confirmation,
        )

    def make_plan(
        self,
        *,
        schema_version: int = 1,
        dry_run: bool = True,
        steps: tuple[PlanStep, ...] | None = None,
    ) -> ExecutionPlan:
        return ExecutionPlan(
            schema_version=schema_version,
            plan_id="plan-hero-run",
            asset_id="hero-run",
            source_preference="auto",
            dry_run=dry_run,
            steps=steps if steps is not None else (self.make_step(),),
        )

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

    def test_schema_version_rejected_on_construction(self) -> None:
        with self.assertRaisesRegex(ValueError, "schema_version must be 1"):
            self.make_plan(schema_version=2)

    def test_constructor_rejects_out_of_order_dependencies(self) -> None:
        with self.assertRaisesRegex(ValueError, "step dependencies must precede step-01"):
            self.make_plan(steps=(self.make_step(depends_on=("step-02",)),))

    def test_from_dict_rejects_non_boolean_dry_run(self) -> None:
        with self.assertRaisesRegex(TypeError, "dry_run must be a boolean"):
            ExecutionPlan.from_dict(
                {
                    "schema_version": 1,
                    "plan_id": "plan-hero-run",
                    "asset_id": "hero-run",
                    "source_preference": "auto",
                    "dry_run": "false",
                    "steps": [
                        {
                            "step_id": "step-01",
                            "action": "check-agent-native",
                            "owner": "agent",
                            "depends_on": [],
                            "requires_confirmation": False,
                        }
                    ],
                }
            )

    def test_from_dict_rejects_non_boolean_requires_confirmation(self) -> None:
        with self.assertRaisesRegex(TypeError, "requires_confirmation must be a boolean"):
            ExecutionPlan.from_dict(
                {
                    "schema_version": 1,
                    "plan_id": "plan-hero-run",
                    "asset_id": "hero-run",
                    "source_preference": "auto",
                    "dry_run": True,
                    "steps": [
                        {
                            "step_id": "step-01",
                            "action": "check-agent-native",
                            "owner": "agent",
                            "depends_on": [],
                            "requires_confirmation": "false",
                        }
                    ],
                }
            )


if __name__ == "__main__":
    unittest.main()
