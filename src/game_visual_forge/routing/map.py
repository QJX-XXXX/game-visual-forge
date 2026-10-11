from __future__ import annotations

from game_visual_forge.contracts import (
    ExternalProvider,
    MapRequest,
    MapSourceCapabilities,
    MapSourceDecision,
    MapSourceType,
    ProviderPreflight,
    SourcePreference,
    TileMapRequest,
)
from game_visual_forge.jobs.fingerprints import fingerprint_request


def _decision(
    request: MapRequest | TileMapRequest,
    source_type: MapSourceType | None,
    *,
    requires_user_selection: bool,
    requires_paid_confirmation: bool,
    reason: str,
    provider: ExternalProvider | None = None,
) -> MapSourceDecision:
    return MapSourceDecision(
        schema_version=1,
        source_type=source_type,
        requires_user_selection=requires_user_selection,
        requires_paid_confirmation=requires_paid_confirmation,
        reason=reason,
        request_fingerprint=fingerprint_request(request.to_dict()),
        selected_provider=provider,
    )


def route_map(
    request: MapRequest | TileMapRequest,
    native: MapSourceCapabilities,
    *,
    selected_source: MapSourceType | None = None,
    provider_preflight: ProviderPreflight | None = None,
) -> MapSourceDecision:
    if request.source_preference is SourcePreference.EXISTING_FILE:
        return _decision(request, MapSourceType.EXISTING_FILE, requires_user_selection=False, requires_paid_confirmation=False, reason="existing-file-supplied")

    if selected_source is MapSourceType.EXISTING_FILE:
        return _decision(request, MapSourceType.EXISTING_FILE, requires_user_selection=False, requires_paid_confirmation=False, reason="user-selected-existing-file")

    native_supported = native.supported and "text-to-image" in native.operations
    if native_supported and request.source_preference in {SourcePreference.AUTO, SourcePreference.AGENT_NATIVE} and selected_source is None:
        return _decision(request, MapSourceType.AGENT_NATIVE, requires_user_selection=False, requires_paid_confirmation=False, reason="agent-native-supported")

    if selected_source is MapSourceType.AGENT_NATIVE:
        if not native_supported:
            return _decision(request, None, requires_user_selection=True, requires_paid_confirmation=False, reason="agent-native-unavailable")
        return _decision(request, MapSourceType.AGENT_NATIVE, requires_user_selection=False, requires_paid_confirmation=False, reason="user-selected-native-retry")

    if selected_source is MapSourceType.LOCAL_TOOL:
        return _decision(request, MapSourceType.LOCAL_TOOL, requires_user_selection=False, requires_paid_confirmation=False, reason="user-selected-local-tool")

    if selected_source in {MapSourceType.JIMENG, MapSourceType.WANXIANG}:
        provider = ExternalProvider(selected_source.value)
        if provider_preflight is None or provider_preflight.provider is not provider:
            raise ValueError("selected map provider requires matching preflight")
        if not provider_preflight.available or not provider_preflight.authenticated:
            return _decision(request, None, requires_user_selection=True, requires_paid_confirmation=False, reason="selected-provider-unavailable", provider=provider)
        return _decision(request, selected_source, requires_user_selection=False, requires_paid_confirmation=True, reason="user-selected-paid-provider", provider=provider)

    return _decision(request, None, requires_user_selection=True, requires_paid_confirmation=False, reason="map-source-selection-required")
