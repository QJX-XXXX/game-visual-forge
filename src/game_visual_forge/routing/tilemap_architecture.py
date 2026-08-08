from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from game_visual_forge.contracts import LayoutStrategy, TileMapRequest, TileSetProfile


COHERENT_FEATURES = frozenset({"watercourse", "bridge", "complex-paths", "paths", "building-pads"})


@dataclass(frozen=True)
class TileMapArchitectureDecision:
    schema_version: int
    asset_id: str
    request_fingerprint: str
    selected_profile: TileSetProfile
    requires_complete_foundation: bool
    continuity_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("architecture decision schema_version must be 1")
        if not self.asset_id or not self.request_fingerprint:
            raise ValueError("architecture decision identity must not be empty")
        if not isinstance(self.selected_profile, TileSetProfile):
            raise TypeError("selected_profile must be TileSetProfile")
        if not isinstance(self.requires_complete_foundation, bool):
            raise TypeError("requires_complete_foundation must be a boolean")
        if not isinstance(self.continuity_reasons, tuple) or not all(isinstance(item, str) for item in self.continuity_reasons):
            raise TypeError("continuity_reasons must be a tuple of strings")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "asset_id": self.asset_id,
            "request_fingerprint": self.request_fingerprint,
            "selected_profile": self.selected_profile.value,
            "requires_complete_foundation": self.requires_complete_foundation,
            "continuity_reasons": list(self.continuity_reasons),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TileMapArchitectureDecision":
        return cls(
            schema_version=int(value["schema_version"]),
            asset_id=str(value["asset_id"]),
            request_fingerprint=str(value["request_fingerprint"]),
            selected_profile=TileSetProfile(value["selected_profile"]),
            requires_complete_foundation=bool(value["requires_complete_foundation"]),
            continuity_reasons=tuple(str(item) for item in value.get("continuity_reasons", [])),
        )


def select_tilemap_architecture(request: TileMapRequest, request_fingerprint: str) -> TileMapArchitectureDecision:
    intake = request.intake
    if intake is None:
        selected = request.tileset_profile
        if selected not in {TileSetProfile.COHERENT_FOUNDATION, TileSetProfile.DEMAND_DRIVEN}:
            selected = TileSetProfile.DEMAND_DRIVEN
        return TileMapArchitectureDecision(1, request.asset_id, request_fingerprint, selected, selected is TileSetProfile.COHERENT_FOUNDATION, ())
    requires_coherent = intake.layout_strategy is LayoutStrategy.FIXED_AUTHORED and bool(COHERENT_FEATURES.intersection(intake.continuity_features))
    selected = TileSetProfile.COHERENT_FOUNDATION if requires_coherent else TileSetProfile.DEMAND_DRIVEN
    if request.tileset_profile not in {TileSetProfile.COHERENT_FOUNDATION, TileSetProfile.DEMAND_DRIVEN}:
        declared = request.tileset_profile
    else:
        declared = request.tileset_profile
    if declared != selected:
        raise ValueError(f"architecture requires {selected.value}, request declares {declared.value}")
    reasons = tuple(item for item in intake.continuity_features if item in COHERENT_FEATURES)
    return TileMapArchitectureDecision(1, request.asset_id, request_fingerprint, selected, requires_coherent, reasons)
