from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol


class MediaKind(StrEnum):
    IMAGE = "image"
    VIDEO = "video"


class ExternalProvider(StrEnum):
    DREAMINA = "dreamina"
    JIMENG = "jimeng"
    MINIMAX = "minimax"
    WANXIANG = "wanxiang"


class ProviderCommand(StrEnum):
    CAPABILITIES = "capabilities"
    MODELS = "models"
    PREFLIGHT = "preflight"
    ESTIMATE = "estimate"
    PREPARE = "prepare"
    SUBMIT = "submit"
    QUERY = "query"
    DOWNLOAD = "download"
    GENERATE = "generate"


@dataclass(frozen=True)
class ProviderPreflight:
    schema_version: int
    provider: ExternalProvider
    available: bool
    authenticated: bool
    executable: str | None
    version: str | None
    account_credit: int | None
    reason: str | None
    backend: str | None = None
    authentication_verified: bool | None = None

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        if self.backend is not None and self.backend not in {"api", "cli", "mcp"}:
            raise ValueError("unsupported provider backend")
        if self.authentication_verified is not None and not isinstance(self.authentication_verified, bool):
            raise ValueError("authentication_verified must be boolean")

    @property
    def ready(self) -> bool:
        return self.available and (self.authenticated or (self.backend in {"cli", "mcp"} and self.authentication_verified is False))

    def to_dict(self) -> dict[str, Any]:
        value = {
            "schema_version": self.schema_version,
            "provider": self.provider.value,
            "available": self.available,
            "authenticated": self.authenticated,
            "executable": self.executable,
            "version": self.version,
            "account_credit": self.account_credit,
            "reason": self.reason,
        }
        if self.backend is not None:
            value["backend"] = self.backend
        if self.authentication_verified is not None:
            value["authentication_verified"] = self.authentication_verified
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ProviderPreflight":
        if not isinstance(value, dict):
            raise TypeError("ProviderPreflight payload must be an object")
        return cls(
            schema_version=value["schema_version"],
            provider=ExternalProvider(value["provider"]),
            available=value["available"],
            authenticated=value["authenticated"],
            executable=value.get("executable"),
            version=value.get("version"),
            account_credit=value.get("account_credit"),
            reason=value.get("reason"),
            backend=value.get("backend"),
            authentication_verified=value.get("authentication_verified"),
        )


@dataclass(frozen=True)
class ProviderCapabilities:
    schema_version: int
    provider: ExternalProvider
    media_kind: MediaKind
    operations: tuple[str, ...]
    asynchronous: bool
    max_outputs: int

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        if self.max_outputs <= 0:
            raise ValueError("max_outputs must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "provider": self.provider.value,
            "media_kind": self.media_kind.value,
            "operations": list(self.operations),
            "asynchronous": self.asynchronous,
            "max_outputs": self.max_outputs,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ProviderCapabilities":
        if not isinstance(value, dict):
            raise TypeError("ProviderCapabilities payload must be an object")
        operations = value["operations"]
        if not isinstance(operations, list):
            raise TypeError("operations must be a JSON array")
        return cls(
            schema_version=value["schema_version"],
            provider=ExternalProvider(value["provider"]),
            media_kind=MediaKind(value["media_kind"]),
            operations=tuple(operations),
            asynchronous=value["asynchronous"],
            max_outputs=value["max_outputs"],
        )


@dataclass(frozen=True)
class CostEstimate:
    schema_version: int
    provider: ExternalProvider
    currency: str | None
    amount: str | None
    verified: bool
    notice: str

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "provider": self.provider.value,
            "currency": self.currency,
            "amount": self.amount,
            "verified": self.verified,
            "notice": self.notice,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "CostEstimate":
        if not isinstance(value, dict):
            raise TypeError("CostEstimate payload must be an object")
        return cls(
            schema_version=value["schema_version"],
            provider=ExternalProvider(value["provider"]),
            currency=value.get("currency"),
            amount=value.get("amount"),
            verified=value["verified"],
            notice=value["notice"],
        )


@dataclass(frozen=True)
class SubmissionReceipt:
    schema_version: int
    provider: ExternalProvider
    external_task_id: str | None
    status: str

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "provider": self.provider.value,
            "external_task_id": self.external_task_id,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SubmissionReceipt":
        if not isinstance(value, dict):
            raise TypeError("SubmissionReceipt payload must be an object")
        return cls(
            schema_version=value["schema_version"],
            provider=ExternalProvider(value["provider"]),
            external_task_id=value.get("external_task_id"),
            status=value["status"],
        )


class CliProviderProtocol(Protocol):
    def preflight(self) -> ProviderPreflight: ...
    def capabilities(self, media_kind: MediaKind) -> ProviderCapabilities: ...
    def models(self, media_kind: MediaKind) -> tuple[str, ...]: ...
    def estimate(self, request: dict[str, Any]) -> CostEstimate: ...
    def submit(self, request: dict[str, Any], *, confirmed: bool) -> SubmissionReceipt: ...
    def query(self, external_task_id: str) -> SubmissionReceipt: ...
    def download(self, external_task_id: str, output_dir: Path) -> tuple[Path, ...]: ...
