from __future__ import annotations

from typing import Any

from tests.test_coherent_foundation_tilemap import coherent_request


def build_workflow_request_payload(*, intake_overrides: dict[str, object] | None = None) -> dict[str, Any]:
    payload = coherent_request().to_dict()
    payload["approval_workflow"] = "two_gate"
    payload["gameplay_crop"] = {"x": 0, "y": 0, "width": 2, "height": 2}
    payload["intake"] = {
        "schema_version": 1,
        "gameplay_actions": ["walk", "collide", "enter-buildings"],
        "walkability_required": True,
        "collision_required": True,
        "enterable_buildings_required": True,
        "triggers_required": True,
        "perspective": "top-down",
        "map_scale": "medium",
        "art_style": "modern-pixel",
        "mood": "spring-sunny-cozy",
        "water_policy": "blocked",
        "bridge_policy": "horizontal-traversable",
        "continuity_features": ["watercourse", "bridge", "paths", "building-pads"],
        "object_identities": ["inn", "shop", "player-home"],
        "entrance_policy": "bottom-center-open",
        "engine_target": "Unity_Tilemap",
        "project_id": "2DMirrorDemo",
        "scene_path": "Assets/Scenes/SampleScene.unity",
        "import_mode": "import_and_place",
        "source_preference": "agent-native",
        "native_generation_allowed": True,
        "paid_provider_allowed": False,
        "targeted_regeneration_allowed": True,
        "layout_strategy": "fixed_authored",
        "requirements_confirmed": False,
        "confirmed_summary_sha256": None,
    }
    payload["intake"].update(intake_overrides or {})
    return payload
