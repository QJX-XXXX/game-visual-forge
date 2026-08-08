from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class LayoutStrategy(StrEnum):
    FIXED_AUTHORED = "fixed_authored"
    REUSABLE = "reusable"
    PROCEDURAL = "procedural"


class TileMapImportMode(StrEnum):
    ASSETS_ONLY = "assets_only"
    IMPORT_AND_PLACE = "import_and_place"


class TileMapIntakeStatus(StrEnum):
    NEEDS_USER_INPUT = "needs_user_input"
    NEEDS_USER_CONFIRMATION = "needs_user_confirmation"
    CONFIRMED = "confirmed"


QUESTION_GROUP_FIELDS: dict[str, tuple[str, ...]] = {
    "gameplay": (
        "gameplay_actions",
        "walkability_required",
        "collision_required",
        "enterable_buildings_required",
        "triggers_required",
    ),
    "visual": ("perspective", "map_scale", "art_style", "mood"),
    "topology": ("water_policy", "bridge_policy", "continuity_features"),
    "objects": ("object_identities", "entrance_policy"),
    "delivery": ("engine_target", "project_id", "scene_path", "import_mode"),
    "source": (
        "source_preference",
        "native_generation_allowed",
        "paid_provider_allowed",
        "targeted_regeneration_allowed",
    ),
}

_GROUP_LABELS = {
    "gameplay": "Player gameplay",
    "visual": "Visual direction",
    "topology": "Terrain topology",
    "objects": "Objects and entrances",
    "delivery": "Engine delivery",
    "source": "Asset source and regeneration",
}


def _required(value: Any) -> bool:
    if value is None or value == "":
        return False
    if isinstance(value, (list, tuple)) and not value:
        return False
    return True


@dataclass(frozen=True)
class TileMapQuestionGroup:
    question_group_id: str
    fields: tuple[str, ...]
    missing_fields: tuple[str, ...]
    label: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.question_group_id,
            "fields": list(self.fields),
            "missing_fields": list(self.missing_fields),
            "label": self.label,
        }


@dataclass(frozen=True)
class TileMapIntake:
    schema_version: int
    gameplay_actions: tuple[str, ...]
    walkability_required: bool
    collision_required: bool
    enterable_buildings_required: bool
    triggers_required: bool
    perspective: str
    map_scale: str
    art_style: str
    mood: str
    water_policy: str
    bridge_policy: str
    continuity_features: tuple[str, ...]
    object_identities: tuple[str, ...]
    entrance_policy: str
    engine_target: str
    project_id: str
    scene_path: str
    import_mode: TileMapImportMode
    source_preference: str
    native_generation_allowed: bool
    paid_provider_allowed: bool
    targeted_regeneration_allowed: bool
    layout_strategy: LayoutStrategy
    requirements_confirmed: bool = False
    confirmed_summary_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("tilemap intake schema_version must be 1")
        for field in (
            "gameplay_actions",
            "continuity_features",
            "object_identities",
        ):
            value = getattr(self, field)
            if not isinstance(value, tuple) or not all(isinstance(item, str) and item for item in value):
                raise TypeError(f"{field} must be a tuple of non-empty strings")
        for field in (
            "walkability_required",
            "collision_required",
            "enterable_buildings_required",
            "triggers_required",
            "native_generation_allowed",
            "paid_provider_allowed",
            "targeted_regeneration_allowed",
            "requirements_confirmed",
        ):
            if not isinstance(getattr(self, field), bool):
                raise TypeError(f"{field} must be a boolean")
        for field in (
            "perspective",
            "map_scale",
            "art_style",
            "mood",
            "water_policy",
            "bridge_policy",
            "entrance_policy",
            "engine_target",
            "project_id",
            "scene_path",
            "source_preference",
        ):
            if not isinstance(getattr(self, field), str) or not getattr(self, field).strip():
                raise ValueError(f"{field} must not be empty")
        if not isinstance(self.import_mode, TileMapImportMode):
            raise TypeError("import_mode must be TileMapImportMode")
        if not isinstance(self.layout_strategy, LayoutStrategy):
            raise TypeError("layout_strategy must be LayoutStrategy")
        if self.confirmed_summary_sha256 is not None and (
            not isinstance(self.confirmed_summary_sha256, str)
            or len(self.confirmed_summary_sha256) != 64
            or any(char not in "0123456789abcdef" for char in self.confirmed_summary_sha256)
        ):
            raise ValueError("confirmed_summary_sha256 must be a lowercase SHA-256 hex digest")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "gameplay_actions": list(self.gameplay_actions),
            "walkability_required": self.walkability_required,
            "collision_required": self.collision_required,
            "enterable_buildings_required": self.enterable_buildings_required,
            "triggers_required": self.triggers_required,
            "perspective": self.perspective,
            "map_scale": self.map_scale,
            "art_style": self.art_style,
            "mood": self.mood,
            "water_policy": self.water_policy,
            "bridge_policy": self.bridge_policy,
            "continuity_features": list(self.continuity_features),
            "object_identities": list(self.object_identities),
            "entrance_policy": self.entrance_policy,
            "engine_target": self.engine_target,
            "project_id": self.project_id,
            "scene_path": self.scene_path,
            "import_mode": self.import_mode.value,
            "source_preference": self.source_preference,
            "native_generation_allowed": self.native_generation_allowed,
            "paid_provider_allowed": self.paid_provider_allowed,
            "targeted_regeneration_allowed": self.targeted_regeneration_allowed,
            "layout_strategy": self.layout_strategy.value,
            "requirements_confirmed": self.requirements_confirmed,
            "confirmed_summary_sha256": self.confirmed_summary_sha256,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TileMapIntake":
        if not isinstance(value, dict):
            raise TypeError("intake must be a JSON object")
        sequence = lambda name: tuple(str(item) for item in value.get(name, []))
        return cls(
            schema_version=int(value.get("schema_version", 1)),
            gameplay_actions=sequence("gameplay_actions"),
            walkability_required=bool(value.get("walkability_required", False)),
            collision_required=bool(value.get("collision_required", False)),
            enterable_buildings_required=bool(value.get("enterable_buildings_required", False)),
            triggers_required=bool(value.get("triggers_required", False)),
            perspective=str(value.get("perspective", "")),
            map_scale=str(value.get("map_scale", "")),
            art_style=str(value.get("art_style", "")),
            mood=str(value.get("mood", "")),
            water_policy=str(value.get("water_policy", "")),
            bridge_policy=str(value.get("bridge_policy", "")),
            continuity_features=sequence("continuity_features"),
            object_identities=sequence("object_identities"),
            entrance_policy=str(value.get("entrance_policy", "")),
            engine_target=str(value.get("engine_target", "")),
            project_id=str(value.get("project_id", "")),
            scene_path=str(value.get("scene_path", "")),
            import_mode=TileMapImportMode(value.get("import_mode", TileMapImportMode.ASSETS_ONLY.value)),
            source_preference=str(value.get("source_preference", "")),
            native_generation_allowed=bool(value.get("native_generation_allowed", False)),
            paid_provider_allowed=bool(value.get("paid_provider_allowed", False)),
            targeted_regeneration_allowed=bool(value.get("targeted_regeneration_allowed", False)),
            layout_strategy=LayoutStrategy(value.get("layout_strategy", LayoutStrategy.REUSABLE.value)),
            requirements_confirmed=bool(value.get("requirements_confirmed", False)),
            confirmed_summary_sha256=value.get("confirmed_summary_sha256"),
        )


@dataclass(frozen=True)
class TileMapIntakeAssessment:
    status: TileMapIntakeStatus
    question_groups: tuple[TileMapQuestionGroup, ...]
    confirmation_summary: str
    confirmation_sha256: str
    intake: TileMapIntake | None


def _canonical_payload(intake: TileMapIntake) -> dict[str, Any]:
    payload = intake.to_dict()
    payload.pop("requirements_confirmed", None)
    payload.pop("confirmed_summary_sha256", None)
    return payload


def canonical_tilemap_confirmation_summary(intake: TileMapIntake) -> str:
    payload = _canonical_payload(intake)
    lines = ["Tilemap requirements confirmation", "Player gameplay: " + ", ".join(payload["gameplay_actions"])]
    for group_id, fields in QUESTION_GROUP_FIELDS.items():
        values = {field: payload[field] for field in fields}
        lines.append(f"{_GROUP_LABELS[group_id]}: " + json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    lines.append("Layout strategy: " + payload["layout_strategy"])
    return "\n".join(lines)


def tilemap_confirmation_sha256(intake: TileMapIntake) -> str:
    return hashlib.sha256(canonical_tilemap_confirmation_summary(intake).encode("utf-8")).hexdigest()


def _assessment_groups(payload: dict[str, Any]) -> tuple[TileMapQuestionGroup, ...]:
    intake_payload = payload.get("intake")
    if not isinstance(intake_payload, dict):
        intake_payload = {}
    groups = []
    for group_id, fields in QUESTION_GROUP_FIELDS.items():
        missing = tuple(field for field in fields if not _required(intake_payload.get(field)))
        if missing:
            groups.append(TileMapQuestionGroup(group_id, fields, missing, _GROUP_LABELS[group_id]))
    return tuple(groups)


def assess_tilemap_intake(payload: dict[str, Any]) -> TileMapIntakeAssessment:
    groups = _assessment_groups(payload)
    intake_payload = payload.get("intake")
    intake = None
    if isinstance(intake_payload, dict) and not groups:
        intake = TileMapIntake.from_dict(intake_payload)
    if groups or intake is None:
        summary = ""
        digest = ""
        if intake is not None:
            summary = canonical_tilemap_confirmation_summary(intake)
            digest = tilemap_confirmation_sha256(intake)
        return TileMapIntakeAssessment(TileMapIntakeStatus.NEEDS_USER_INPUT, groups, summary, digest, intake)
    summary = canonical_tilemap_confirmation_summary(intake)
    digest = tilemap_confirmation_sha256(intake)
    status = TileMapIntakeStatus.CONFIRMED if intake.requirements_confirmed and intake.confirmed_summary_sha256 == digest else TileMapIntakeStatus.NEEDS_USER_CONFIRMATION
    return TileMapIntakeAssessment(status, (), summary, digest, intake)
