from __future__ import annotations

from typing import Any

from game_visual_forge.contracts.audio import AudioRequest, AudioRouteDecision, route_audio as _route_audio


def route_audio(request: AudioRequest, preflight: Any | None) -> AudioRouteDecision:
    return _route_audio(request, preflight)
