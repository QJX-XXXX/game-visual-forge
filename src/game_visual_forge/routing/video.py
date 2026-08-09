from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from game_visual_forge.contracts.provider import ExternalProvider
from game_visual_forge.contracts.video import VideoSourceDecision, VideoSourcePreference, VideoSpriteRequest
from game_visual_forge.contracts.video_provider import VideoProviderBackend
from game_visual_forge.jobs.fingerprints import fingerprint_request


def _provider(value: str | ExternalProvider) -> ExternalProvider:
    return value if isinstance(value, ExternalProvider) else ExternalProvider(value)


def _backend(value: str | VideoProviderBackend) -> VideoProviderBackend:
    return value if isinstance(value, VideoProviderBackend) else VideoProviderBackend(value)


def route_video(
    request: VideoSpriteRequest,
    *,
    selected_provider: ExternalProvider | str | None = None,
    selected_backend: VideoProviderBackend | str | None = None,
    available_backends: Mapping[str | ExternalProvider, Sequence[str | VideoProviderBackend]] | None = None,
) -> VideoSourceDecision:
    fingerprint = fingerprint_request(request.to_dict())
    if request.source_preference is VideoSourcePreference.EXISTING_FILE:
        return VideoSourceDecision(1, fingerprint, request.source_preference, None, None, False, False, "existing-file-supplied")

    provider = _provider(selected_provider or request.provider) if (selected_provider or request.provider) is not None else None
    if provider is None and request.source_preference is not None:
        provider = _provider(request.source_preference.value)
    if provider is None:
        return VideoSourceDecision(1, fingerprint, request.source_preference, None, None, True, False, "provider-selection-required")
    if request.source_preference is not None and request.source_preference.value != provider.value:
        raise ValueError("selected provider does not match source_preference")

    backend_value = selected_backend or request.backend
    if backend_value is None:
        return VideoSourceDecision(1, fingerprint, request.source_preference, provider, None, True, False, "backend-selection-required")
    backend = _backend(backend_value)
    if available_backends is None:
        return VideoSourceDecision(1, fingerprint, request.source_preference, provider, backend, True, False, "provider-preflight-required")
    choices = None
    for key, value in available_backends.items():
        if _provider(key) is provider:
            choices = tuple(_backend(item) for item in value)
            break
    if choices is None or backend not in choices:
        return VideoSourceDecision(1, fingerprint, request.source_preference, provider, backend, True, False, "selected-backend-unavailable")
    return VideoSourceDecision(1, fingerprint, request.source_preference, provider, backend, False, True, "explicit-paid-provider-route")
