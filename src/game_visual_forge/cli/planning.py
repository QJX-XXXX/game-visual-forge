from __future__ import annotations

from game_visual_forge.contracts.asset import AssetBrief, SourcePreference
from game_visual_forge.contracts.execution import ExecutionPlan, PlanStep
from game_visual_forge.contracts.sprite import SourceDecision, SourceType, SpriteRequest
from game_visual_forge.contracts.map import MapRequest
from game_visual_forge.contracts.tilemap import TileMapRequest


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


def execution_plan_from_actions(
    asset_id: str,
    source_preference: str,
    actions: tuple[tuple[str, str, bool], ...],
) -> ExecutionPlan:
    steps = tuple(
        PlanStep(
            step_id=f"step-{index:02d}",
            action=action,
            owner=owner,
            depends_on=(f"step-{index - 1:02d}",) if index > 1 else (),
            requires_confirmation=requires_confirmation,
        )
        for index, (action, owner, requires_confirmation) in enumerate(actions, start=1)
    )
    return ExecutionPlan(1, f"plan-{asset_id}", asset_id, source_preference, True, steps)


def build_sprite_execution_plan(
    request: SpriteRequest,
    decision: SourceDecision | None = None,
) -> ExecutionPlan:
    source = decision.source_type if decision else None
    if source in {SourceType.DREAMINA, SourceType.WANXIANG}:
        actions = (
            ("preflight-provider", "provider-cli", False),
            ("estimate-provider-cost", "provider-cli", False),
            ("prepare-provider-request", "provider-cli", False),
            ("confirm-paid-submit", "agent", True),
            ("submit-provider-request", "provider-cli", False),
            ("query-provider-task", "provider-cli", False),
            ("download-provider-media", "provider-cli", False),
            ("ingest-local-image", "local-runtime", False),
            ("process-local-sprite", "local-runtime", False),
            ("validate-local-artifacts", "local-runtime", False),
        )
    else:
        actions = (
            ("route-image-source", "agent", False),
            ("obtain-local-image", "agent", False),
            ("ingest-local-image", "local-runtime", False),
            ("process-local-sprite", "local-runtime", False),
            ("validate-local-artifacts", "local-runtime", False),
        )
    return execution_plan_from_actions(request.asset_id, request.source_preference.value, actions)


def build_map_execution_plan(request: MapRequest) -> ExecutionPlan:
    if request.source_preference in {SourcePreference.JIMENG, SourcePreference.WANXIANG}:
        actions = (
            ("route-map-source", "agent", False),
            ("preflight-provider", "provider-cli", False),
            ("estimate-provider-cost", "provider-cli", False),
            ("confirm-paid-submit", "agent", True),
            ("obtain-local-map", "provider-cli", False),
            ("ingest-local-map", "local-runtime", False),
            ("process-map-runtime-data", "local-runtime", False),
            ("validate-map-artifacts", "local-runtime", False),
        )
    else:
        actions = (
            ("route-map-source", "agent", False),
            ("obtain-local-map", "agent", False),
            ("ingest-local-map", "local-runtime", False),
            ("process-map-runtime-data", "local-runtime", False),
            ("validate-map-artifacts", "local-runtime", False),
        )
    return execution_plan_from_actions(request.asset_id, request.source_preference.value, actions)


def build_tilemap_execution_plan(request: TileMapRequest) -> ExecutionPlan:
    if request.source_preference in {SourcePreference.JIMENG, SourcePreference.WANXIANG}:
        source_actions = (
            ("route-tileset-source", "agent", False),
            ("preflight-provider", "provider-cli", False),
            ("estimate-provider-cost", "provider-cli", False),
            ("confirm-paid-submit", "agent", True),
            ("obtain-local-tileset", "provider-cli", False),
        )
    else:
        source_actions = (
            ("route-tileset-source", "agent", False),
            ("obtain-local-tileset", "agent", False),
        )
    obtain_action = "obtain-local-tileset-pages" if request.tileset_profile.value == "adaptive_hd" else "obtain-local-tileset"
    if source_actions[-1][0] == "obtain-local-tileset":
        source_actions = source_actions[:-1] + ((obtain_action, source_actions[-1][1], source_actions[-1][2]),)
    actions = source_actions + (
        ("ingest-local-tileset", "local-runtime", False),
        ("slice-and-compose-tilemap", "local-runtime", False),
        ("emit-unity-tilemap-bundle", "local-runtime", False),
        ("validate-tilemap-artifacts", "local-runtime", False),
    )
    return execution_plan_from_actions(request.asset_id, request.source_preference.value, actions)
