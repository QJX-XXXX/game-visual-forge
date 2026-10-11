from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any
from .music import music_hash


class MusicProvider(StrEnum):
    COMFYUI_MUSIC3 = "comfyui-music3"
    SUNO_API = "suno-api"
    STABLE_AUDIO_API = "stable-audio-api"


def scan_safe(value: Any):
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            if any(word in normalized for word in ("token", "cookie", "authorization", "api_key", "secret", "base64")):
                raise ValueError("secret field cannot be persisted")
            scan_safe(item)
    elif isinstance(value, (tuple, list)):
        for item in value:
            scan_safe(item)
    elif isinstance(value, str) and (";base64," in value.lower() or "bearer " in value.lower()):
        raise ValueError("secret or inline media cannot be persisted")


@dataclass(frozen=True)
class MusicProviderCapability:
    provider: MusicProvider
    model: str | None
    official_source: str
    verified_at: str
    is_paid: bool
    available: bool
    schema_verified: bool
    auth_verified: bool
    rights_status: str
    duration_bounds: tuple[float, float] | None
    vocal_modes: tuple[str, ...]
    output_formats: tuple[str, ...]
    submission_mode: str
    id_recovery: bool
    pricing_status: str
    credits_per_submission: float | None = None
    candidates_per_submission: int | None = 1
    reason: str = ""

    def to_dict(self):
        return asdict(self)

    @property
    def sha256(self):
        return music_hash(self.to_dict())

    @classmethod
    def from_dict(cls, value):
        values = dict(value)
        values["provider"] = MusicProvider(values["provider"])
        for key in ("vocal_modes", "output_formats"):
            values[key] = tuple(values[key])
        if values["duration_bounds"] is not None:
            values["duration_bounds"] = tuple(values["duration_bounds"])
        return cls(**values)


class MusicAttemptStatus(StrEnum):
    PREPARED = "prepared"
    SUBMITTING = "submitting"
    SUBMITTED = "submitted"
    RUNNING = "running"
    COMPLETED = "completed"
    DOWNLOADED = "downloaded"
    FAILED = "failed"
    SUBMISSION_UNKNOWN = "submission_unknown"
    NEEDS_USER_ACTION = "needs_user_action"


@dataclass(frozen=True)
class MusicGenerationAttempt:
    schema_version: int
    attempt_id: str
    request_fingerprint: str
    provider: MusicProvider
    model: str | None
    capability_sha256: str
    parameters: dict[str, Any]
    parameters_sha256: str
    generation_fingerprint: str
    candidate_count: int
    status: MusicAttemptStatus
    is_paid: bool
    created_at: str
    updated_at: str
    external_task_id: str | None = None
    submission_count: int = 0
    returned_candidate_count: int = 0
    error_code: str | None = None
    estimated_credits: float | None = None

    def to_dict(self):
        value = asdict(self)
        value["provider"] = self.provider.value
        value["status"] = self.status.value
        return value

    @classmethod
    def from_dict(cls, value):
        values = dict(value)
        values["provider"] = MusicProvider(values["provider"])
        values["status"] = MusicAttemptStatus(values["status"])
        values["parameters"] = dict(values["parameters"])
        return cls(**values)


@dataclass(frozen=True)
class MusicPaidConfirmation:
    schema_version: int
    provider: MusicProvider
    model: str | None
    capability_sha256: str
    generation_fingerprint: str
    parameters_sha256: str
    request_fingerprint: str
    submission_count: int
    expected_candidate_count: int
    estimated_credits: float | None
    confirmed_at: str
    consumed: bool = False

    @classmethod
    def for_attempt(cls, attempt, *, confirmed_at):
        return cls(1, attempt.provider, attempt.model, attempt.capability_sha256, attempt.generation_fingerprint, attempt.parameters_sha256, attempt.request_fingerprint, 1, attempt.candidate_count, attempt.estimated_credits, confirmed_at)

    def to_dict(self):
        value = asdict(self)
        value["provider"] = self.provider.value
        return value

    @classmethod
    def from_dict(cls, value):
        values = dict(value)
        values["provider"] = MusicProvider(values["provider"])
        return cls(**values)


@dataclass(frozen=True)
class MusicProviderReceipt:
    status: str
    external_task_id: str | None = None
    candidate_ids: tuple[str, ...] = ()
    error_code: str | None = None
    returned_candidate_count: int = 0

    def __post_init__(self):
        if self.status not in {"submitted", "running", "completed", "failed", "submission_unknown"}:
            raise ValueError("invalid provider receipt status")

    def to_dict(self):
        value = asdict(self)
        value["candidate_ids"] = list(self.candidate_ids)
        return value

    @classmethod
    def from_dict(cls, value):
        return cls(value["status"], value.get("external_task_id"), tuple(value.get("candidate_ids", ())), value.get("error_code"), int(value.get("returned_candidate_count", 0)))


@dataclass(frozen=True)
class MusicHttpResponse:
    status_code: int
    headers: dict[str, str]
    body: bytes


@dataclass(frozen=True)
class MusicDownloadedFile:
    path: str
    sha256: str
    provider_candidate_id: str


@dataclass(frozen=True)
class MusicWorkflowReport:
    workflow_sha256: str
    expanded_node_types: tuple[str, ...]
    model_names: tuple[str, ...]
    local_only: bool
    spends_credits: bool
    slots: tuple[str, ...]
    ready: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self):
        return asdict(self)


def default_music_capabilities(*, local_ready=False):
    local = MusicProviderCapability(MusicProvider.COMFYUI_MUSIC3, "minimax-music3", "https://github.com/MiniMax-AI/MiniMax-Music3", "2026-10-10", False, local_ready, True, True, "model-license-required", (0.04, 360), ("instrumental", "vocals-allowed", "vocals-required"), ("wav",), "comfy-mcp", True, "local-no-api-charge", reason="local workflow report required")
    stable = MusicProviderCapability(MusicProvider.STABLE_AUDIO_API, "stable-audio-3", "https://platform.stability.ai/docs/api-reference", "2026-10-10", True, True, True, False, "documented-game-use", (1, 380), ("instrumental",), ("wav", "mp3"), "async", True, "dated-estimate", 26, 1, "credential and account verification required")
    suno = MusicProviderCapability(MusicProvider.SUNO_API, None, "https://platform.suno.com/", "2026-10-10", True, False, False, False, "unknown", None, (), (), "unknown", False, "unknown", None, None, "official API schema, account terms and pricing are not yet verified")
    return {c.provider: c for c in (local, suno, stable)}
