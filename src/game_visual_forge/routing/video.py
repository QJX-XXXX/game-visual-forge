from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from game_visual_forge.contracts.provider import ExternalProvider
from game_visual_forge.contracts.video import VideoSourceDecision, VideoSourcePreference, VideoSpriteRequest
from game_visual_forge.contracts.video_provider import VideoProviderBackend
from game_visual_forge.jobs.fingerprints import fingerprint_request


COMFYUI_H3_BACKEND = "comfy-mcp"


def _provider(value: str | ExternalProvider) -> ExternalProvider:
    return value if isinstance(value, ExternalProvider) else ExternalProvider(value)


def _backend(value: str | VideoProviderBackend) -> VideoProviderBackend:
    return value if isinstance(value, VideoProviderBackend) else VideoProviderBackend(value)


def _text(value: object) -> str:
    return str(value.value) if hasattr(value, "value") else str(value)


def _route_comfyui_h3(
    request: VideoSpriteRequest,
    fingerprint: str,
    *,
    selected_provider: ExternalProvider | str | None,
    selected_backend: VideoProviderBackend | str | None,
    available_backends: Mapping[str | ExternalProvider, Sequence[str | VideoProviderBackend]] | None,
) -> VideoSourceDecision:
    if selected_provider is not None and _text(selected_provider) != VideoSourcePreference.COMFYUI_H3.value:
        raise ValueError("selected provider does not match source_preference")
    if request.provider is not None:
        raise ValueError("provider must be omitted for the local comfyui-h3 route")
    backend = None if (selected_backend or request.backend) is None else _text(selected_backend or request.backend)
    if backend is None:
        return VideoSourceDecision(1, fingerprint, request.source_preference, None, None, True, False, "backend-selection-required")
    if available_backends is None:
        return VideoSourceDecision(1, fingerprint, request.source_preference, None, backend, True, False, "comfyui-preflight-required")
    choices: tuple[str, ...] | None = None
    for key, value in available_backends.items():
        if _text(key) == VideoSourcePreference.COMFYUI_H3.value:
            choices = tuple(_text(item) for item in value)
            break
    if backend != COMFYUI_H3_BACKEND or choices is None or backend not in choices:
        return VideoSourceDecision(1, fingerprint, request.source_preference, None, backend, True, False, "selected-backend-unavailable")
    return VideoSourceDecision(1, fingerprint, request.source_preference, None, backend, False, False, "explicit-local-comfyui-h3-route")


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
    if request.source_preference is VideoSourcePreference.COMFYUI_H3:
        return _route_comfyui_h3(
            request,
            fingerprint,
            selected_provider=selected_provider,
            selected_backend=selected_backend,
            available_backends=available_backends,
        )

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
