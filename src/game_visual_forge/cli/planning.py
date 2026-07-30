from __future__ import annotations

from game_visual_forge.contracts.asset import AssetBrief, SourcePreference
from game_visual_forge.contracts.execution import ExecutionPlan, PlanStep


SEQUENCES: dict[SourcePreference, tuple[tuple[str, str, bool], ...]] = {
    SourcePreference.AUTO: (
        ("check-agent-native", "agent", False),
        ("generate-agent-native", "agent", False),
        ("inspect-generated-media", "agent", False),
        ("postprocess-local", "local-runtime", False),
        ("validate-delivery", "agent", False),
    ),
    SourcePreference.AGENT_NATIVE: (
        ("generate-agent-native", "agent", False),
        ("inspect-generated-media", "agent", False),
        ("postprocess-local", "local-runtime", False),
        ("validate-delivery", "agent", False),
    ),
    SourcePreference.JIMENG: (
        ("preflight-provider", "provider-cli", False),
        ("confirm-paid-submit", "agent", True),
        ("generate-provider-media", "provider-cli", False),
        ("inspect-generated-media", "agent", False),
        ("postprocess-local", "local-runtime", False),
        ("validate-delivery", "agent", False),
    ),
    SourcePreference.WANXIANG: (
        ("preflight-provider", "provider-cli", False),
        ("confirm-paid-submit", "agent", True),
        ("generate-provider-media", "provider-cli", False),
        ("inspect-generated-media", "agent", False),
        ("postprocess-local", "local-runtime", False),
        ("validate-delivery", "agent", False),
    ),
    SourcePreference.EXISTING_FILE: (
        ("validate-existing-media", "local-runtime", False),
        ("postprocess-local", "local-runtime", False),
        ("validate-delivery", "agent", False),
    ),
}


def build_execution_plan(brief: AssetBrief) -> ExecutionPlan:
    steps: list[PlanStep] = []
    previous_step_id: str | None = None
    for index, (action, owner, requires_confirmation) in enumerate(
        SEQUENCES[brief.source_preference],
        start=1,
    ):
        step_id = f"step-{index:02d}"
        steps.append(
            PlanStep(
                step_id=step_id,
                action=action,
                owner=owner,
                depends_on=(previous_step_id,) if previous_step_id else (),
                requires_confirmation=requires_confirmation,
            )
        )
        previous_step_id = step_id
    plan = ExecutionPlan(
        schema_version=1,
        plan_id=f"plan-{brief.asset_id}",
        asset_id=brief.asset_id,
        source_preference=brief.source_preference.value,
        dry_run=True,
        steps=tuple(steps),
    )
    plan.validate()
    return plan
