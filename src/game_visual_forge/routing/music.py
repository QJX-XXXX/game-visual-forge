from game_visual_forge.contracts.music import MusicRouteDecision
from game_visual_forge.contracts.music_provider import MusicProvider


def route_music(request, capabilities, selection=None):
    selected = MusicProvider(selection) if selection is not None else MusicProvider.COMFYUI_MUSIC3
    cap = capabilities.get(selected)
    if cap is None or not cap.available or not cap.schema_verified:
        return MusicRouteDecision(selected, "needs_user_action", cap.reason if cap else "official capability snapshot required", False)
    if request.vocal_policy.value not in cap.vocal_modes or (request.lyrics is not None and selected is MusicProvider.STABLE_AUDIO_API):
        return MusicRouteDecision(selected, "unsupported_requirement", "selected provider does not support the explicit vocal or lyric requirement", False)
    if cap.duration_bounds is None or not cap.duration_bounds[0] <= request.target_duration_seconds <= cap.duration_bounds[1]:
        return MusicRouteDecision(selected, "unsupported_requirement", "duration is outside the verified provider bounds", False)
    if cap.is_paid and (not cap.auth_verified or cap.rights_status == "unknown" or cap.pricing_status == "unknown"):
        return MusicRouteDecision(selected, "needs_user_action", "official account, rights and pricing verification required", True)
    return MusicRouteDecision(selected, "ready", "verified provider selected", cap.is_paid)
