from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any

from .pathing import normalize_repo_relative_path
from .provider import CostEstimate, ExternalProvider
from .video import VideoGenerationMode


_DIGEST = re.compile(r"[0-9a-f]{64}")
_SECRET_KEYS = {"token", "cookie", "authorization", "api_key", "access_key", "secret", "signed_url", "base64"}


def _digest(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise ValueError(f"{field} must be a SHA-256 hex digest")
    return value


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must not be empty")
    return value


def _timestamp(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field} must be a UTC RFC 3339 timestamp")
    return value


def _scan_safe(value: Any, path: str = "parameters") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in _SECRET_KEYS:
                raise ValueError(f"secret field is not allowed: {path}.{key}")
            _scan_safe(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _scan_safe(child, f"{path}[{index}]")
    elif isinstance(value, str):
        lowered = value.lower()
        if "data:" in lowered and ";base64," in lowered:
            raise ValueError(f"base64 media is not allowed: {path}")
        if "signed" in lowered and "http" in lowered:
            raise ValueError(f"signed URL is not allowed: {path}")


class VideoProviderBackend(StrEnum):
    API = "api"
    CLI = "cli"


class VideoModelSupport(StrEnum):
    PROFILED = "profiled"
    DISCOVERED_UNPROFILED = "discovered-unprofiled"
    HISTORICAL = "historical"


class VideoAttemptStatus(StrEnum):
    PREPARED = "prepared"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    SUBMITTING = "submitting"
    SUBMITTED = "submitted"
    RUNNING = "running"
    COMPLETED = "completed"
    DOWNLOADED = "downloaded"
    SUBMISSION_UNKNOWN = "submission_unknown"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class VideoModelProfile:
    schema_version: int
    provider: ExternalProvider
    model: str
    endpoint_generation: str
    endpoint: str
    supported_modes: tuple[VideoGenerationMode, ...]
    reference_roles: tuple[str, ...]
    durations: tuple[int, ...]
    resolutions: tuple[str, ...]
    aspect_ratios: tuple[str, ...]
    audio_supported: bool
    supported_backends: tuple[VideoProviderBackend, ...]
    profile_revision: str
    support: VideoModelSupport = VideoModelSupport.PROFILED

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        _string(self.model, "model")
        _string(self.endpoint_generation, "endpoint_generation")
        _string(self.endpoint, "endpoint")
        if self.support is VideoModelSupport.PROFILED and not self.supported_modes:
            raise ValueError("profiled models require supported modes")
        if not self.supported_backends:
            raise ValueError("supported_backends must not be empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "provider": self.provider.value,
            "model": self.model,
            "endpoint_generation": self.endpoint_generation,
            "endpoint": self.endpoint,
            "supported_modes": [item.value for item in self.supported_modes],
            "reference_roles": list(self.reference_roles),
            "durations": list(self.durations),
            "resolutions": list(self.resolutions),
            "aspect_ratios": list(self.aspect_ratios),
            "audio_supported": self.audio_supported,
            "supported_backends": [item.value for item in self.supported_backends],
            "profile_revision": self.profile_revision,
            "support": self.support.value,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "VideoModelProfile":
        return cls(
            schema_version=int(value["schema_version"]),
            provider=ExternalProvider(value["provider"]),
            model=_string(value["model"], "model"),
            endpoint_generation=_string(value["endpoint_generation"], "endpoint_generation"),
            endpoint=_string(value["endpoint"], "endpoint"),
            supported_modes=tuple(VideoGenerationMode(item) for item in value.get("supported_modes", [])),
            reference_roles=tuple(str(item) for item in value.get("reference_roles", [])),
            durations=tuple(int(item) for item in value.get("durations", [])),
            resolutions=tuple(str(item) for item in value.get("resolutions", [])),
            aspect_ratios=tuple(str(item) for item in value.get("aspect_ratios", [])),
            audio_supported=bool(value.get("audio_supported", False)),
            supported_backends=tuple(VideoProviderBackend(item) for item in value.get("supported_backends", [])),
            profile_revision=_string(value["profile_revision"], "profile_revision"),
            support=VideoModelSupport(value.get("support", "profiled")),
        )


@dataclass(frozen=True)
class VideoModelCatalogSnapshot:
    schema_version: int
    provider: ExternalProvider
    backend: VideoProviderBackend
    region: str
    refreshed_at: str
    adapter_version: str
    models: tuple[VideoModelProfile, ...]
    source: str
    snapshot_sha256: str

    @classmethod
    def create(cls, *, provider: ExternalProvider, backend: VideoProviderBackend, region: str, refreshed_at: str, adapter_version: str, models: tuple[VideoModelProfile | dict[str, Any], ...], source: str) -> "VideoModelCatalogSnapshot":
        normalized: list[VideoModelProfile] = []
        for item in models:
            if isinstance(item, VideoModelProfile):
                normalized.append(item)
            else:
                model_id = _string(item["model"], "models[].model")
                normalized.append(VideoModelProfile(
                    schema_version=1, provider=provider, model=model_id,
                    endpoint_generation="unknown", endpoint="unknown",
                    supported_modes=(), reference_roles=(), durations=(),
                    resolutions=(), aspect_ratios=(), audio_supported=False,
                    supported_backends=(backend,), profile_revision="discovery",
                    support=VideoModelSupport.DISCOVERED_UNPROFILED,
                ))
        payload = {"schema_version": 1, "provider": provider.value, "backend": backend.value, "region": region, "refreshed_at": refreshed_at, "adapter_version": adapter_version, "models": [item.to_dict() for item in normalized], "source": source}
        digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        return cls(1, provider, backend, region, refreshed_at, adapter_version, tuple(normalized), source, digest)

    def model(self, model_id: str) -> VideoModelProfile:
        for item in self.models:
            if item.model == model_id:
                return item
        raise ValueError(f"model not found in snapshot: {model_id}")

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": 1, "provider": self.provider.value, "backend": self.backend.value, "region": self.region, "refreshed_at": self.refreshed_at, "adapter_version": self.adapter_version, "models": [item.to_dict() for item in self.models], "source": self.source, "snapshot_sha256": self.snapshot_sha256}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "VideoModelCatalogSnapshot":
        result = cls.create(provider=ExternalProvider(value["provider"]), backend=VideoProviderBackend(value["backend"]), region=str(value["region"]), refreshed_at=str(value["refreshed_at"]), adapter_version=str(value["adapter_version"]), models=tuple(VideoModelProfile.from_dict(item) for item in value["models"]), source=str(value["source"]))
        if result.snapshot_sha256 != value["snapshot_sha256"]:
            raise ValueError("model catalog snapshot hash does not match")
        return result


@dataclass(frozen=True)
class VideoPaidConfirmation:
    schema_version: int
    attempt_id: str
    provider: ExternalProvider
    backend: VideoProviderBackend
    region: str
    model: str
    model_snapshot_sha256: str
    mode: VideoGenerationMode
    parameters: dict[str, Any]
    reference_sha256: tuple[str, ...]
    quantity: int
    estimate: CostEstimate
    estimate_acknowledged: bool
    request_fingerprint: str
    confirmed_at: str
    binding_fingerprint: str
    consumed_at: str | None = None

    @classmethod
    def create(cls, *, attempt_id: str, provider: ExternalProvider, backend: VideoProviderBackend, region: str, model: str, model_snapshot_sha256: str, mode: VideoGenerationMode, parameters: dict[str, Any], reference_sha256: tuple[str, ...], quantity: int, estimate: CostEstimate, request_fingerprint: str, confirmed_at: str, estimate_acknowledged: bool = False) -> "VideoPaidConfirmation":
        if not estimate.verified and not estimate_acknowledged:
            raise ValueError("unverified estimate requires acknowledgement")
        binding = cls._binding(attempt_id=attempt_id, provider=provider, backend=backend, region=region, model=model, model_snapshot_sha256=model_snapshot_sha256, mode=mode, parameters=parameters, reference_sha256=reference_sha256, quantity=quantity, estimate=estimate, request_fingerprint=request_fingerprint)
        return cls(1, attempt_id, provider, backend, region, model, model_snapshot_sha256, mode, parameters, reference_sha256, quantity, estimate, estimate_acknowledged, request_fingerprint, _timestamp(confirmed_at, "confirmed_at"), cls._hash(binding))

    @staticmethod
    def _hash(value: dict[str, Any]) -> str:
        return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    @classmethod
    def _binding(cls, **values: Any) -> dict[str, Any]:
        _scan_safe(values["parameters"])
        if values["quantity"] <= 0:
            raise ValueError("quantity must be positive")
        _digest(values["model_snapshot_sha256"], "model_snapshot_sha256")
        _digest(values["request_fingerprint"], "request_fingerprint")
        return {key: (value.value if isinstance(value, (ExternalProvider, VideoProviderBackend, VideoGenerationMode)) else value.to_dict() if isinstance(value, CostEstimate) else list(value) if isinstance(value, tuple) else value) for key, value in values.items()}

    def _assert_binding(self, **values: Any) -> None:
        if self._hash(self._binding(**values)) != self.binding_fingerprint:
            raise ValueError("confirmation binding does not match")

    def assert_binding_matches(self, **values: Any) -> None:
        self._assert_binding(**values)

    def authorize_attempt(self, *, now: str, **values: Any) -> "VideoPaidConfirmation":
        if self.consumed_at is not None:
            raise ValueError("confirmation already consumed")
        self._assert_binding(**values)
        return replace(self, consumed_at=_timestamp(now, "consumed_at"))

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": 1, "attempt_id": self.attempt_id, "provider": self.provider.value, "backend": self.backend.value, "region": self.region, "model": self.model, "model_snapshot_sha256": self.model_snapshot_sha256, "mode": self.mode.value, "parameters": self.parameters, "reference_sha256": list(self.reference_sha256), "quantity": self.quantity, "estimate": self.estimate.to_dict(), "estimate_acknowledged": self.estimate_acknowledged, "request_fingerprint": self.request_fingerprint, "confirmed_at": self.confirmed_at, "binding_fingerprint": self.binding_fingerprint, "consumed_at": self.consumed_at}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "VideoPaidConfirmation":
        result = cls(schema_version=int(value["schema_version"]), attempt_id=str(value["attempt_id"]), provider=ExternalProvider(value["provider"]), backend=VideoProviderBackend(value["backend"]), region=str(value["region"]), model=str(value["model"]), model_snapshot_sha256=str(value["model_snapshot_sha256"]), mode=VideoGenerationMode(value["mode"]), parameters=dict(value["parameters"]), reference_sha256=tuple(str(item) for item in value.get("reference_sha256", [])), quantity=int(value["quantity"]), estimate=CostEstimate.from_dict(value["estimate"]), estimate_acknowledged=bool(value.get("estimate_acknowledged", False)), request_fingerprint=str(value["request_fingerprint"]), confirmed_at=str(value["confirmed_at"]), binding_fingerprint=str(value["binding_fingerprint"]), consumed_at=value.get("consumed_at"))
        result._assert_binding(attempt_id=result.attempt_id, provider=result.provider, backend=result.backend, region=result.region, model=result.model, model_snapshot_sha256=result.model_snapshot_sha256, mode=result.mode, parameters=result.parameters, reference_sha256=result.reference_sha256, quantity=result.quantity, estimate=result.estimate, request_fingerprint=result.request_fingerprint)
        return result


@dataclass(frozen=True)
class VideoGenerationAttempt:
    schema_version: int
    attempt_id: str
    request_fingerprint: str
    provider: ExternalProvider
    backend: VideoProviderBackend
    region: str
    model: str
    model_snapshot_sha256: str
    parameters: dict[str, Any]
    status: VideoAttemptStatus
    created_at: str
    updated_at: str
    external_task_id: str | None = None
    downloaded_path: str | None = None
    downloaded_sha256: str | None = None
    error_code: str | None = None
    confirmation_binding_fingerprint: str | None = None

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        _string(self.attempt_id, "attempt_id")
        _digest(self.request_fingerprint, "request_fingerprint")
        _digest(self.model_snapshot_sha256, "model_snapshot_sha256")
        _scan_safe(self.parameters)
        _timestamp(self.created_at, "created_at")
        _timestamp(self.updated_at, "updated_at")
        if self.downloaded_path is not None:
            object.__setattr__(self, "downloaded_path", normalize_repo_relative_path(self.downloaded_path, field_name="downloaded_path"))
        if self.downloaded_sha256 is not None:
            _digest(self.downloaded_sha256, "downloaded_sha256")
        if self.confirmation_binding_fingerprint is not None:
            _digest(self.confirmation_binding_fingerprint, "confirmation_binding_fingerprint")

    def replace(self, **changes: Any) -> "VideoGenerationAttempt":
        immutable = {"provider", "backend", "region", "model", "model_snapshot_sha256", "request_fingerprint", "attempt_id"}
        if immutable.intersection(changes):
            raise ValueError("provider/backend/model binding cannot change after preparation")
        return replace(self, **changes)

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": 1, "attempt_id": self.attempt_id, "request_fingerprint": self.request_fingerprint, "provider": self.provider.value, "backend": self.backend.value, "region": self.region, "model": self.model, "model_snapshot_sha256": self.model_snapshot_sha256, "parameters": self.parameters, "status": self.status.value, "created_at": self.created_at, "updated_at": self.updated_at, "external_task_id": self.external_task_id, "downloaded_path": self.downloaded_path, "downloaded_sha256": self.downloaded_sha256, "error_code": self.error_code, "confirmation_binding_fingerprint": self.confirmation_binding_fingerprint}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "VideoGenerationAttempt":
        return cls(schema_version=int(value["schema_version"]), attempt_id=str(value["attempt_id"]), request_fingerprint=str(value["request_fingerprint"]), provider=ExternalProvider(value["provider"]), backend=VideoProviderBackend(value["backend"]), region=str(value["region"]), model=str(value["model"]), model_snapshot_sha256=str(value["model_snapshot_sha256"]), parameters=dict(value["parameters"]), status=VideoAttemptStatus(value["status"]), created_at=str(value["created_at"]), updated_at=str(value["updated_at"]), external_task_id=value.get("external_task_id"), downloaded_path=value.get("downloaded_path"), downloaded_sha256=value.get("downloaded_sha256"), error_code=value.get("error_code"), confirmation_binding_fingerprint=value.get("confirmation_binding_fingerprint"))
