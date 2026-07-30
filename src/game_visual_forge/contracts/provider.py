from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol


class MediaKind(StrEnum):
    IMAGE = "image"
    VIDEO = "video"


class ExternalProvider(StrEnum):
    JIMENG = "jimeng"
    WANXIANG = "wanxiang"


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

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "provider": self.provider.value,
            "available": self.available,
            "authenticated": self.authenticated,
            "executable": self.executable,
            "version": self.version,
            "account_credit": self.account_credit,
            "reason": self.reason,
        }


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


@dataclass(frozen=True)
class SubmissionReceipt:
    schema_version: int
    provider: ExternalProvider
    external_task_id: str | None
    status: str

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")


class CliProviderProtocol(Protocol):
    def preflight(self) -> ProviderPreflight: ...
    def capabilities(self, media_kind: MediaKind) -> ProviderCapabilities: ...
    def models(self, media_kind: MediaKind) -> tuple[str, ...]: ...
    def estimate(self, request: dict[str, Any]) -> CostEstimate: ...
    def submit(self, request: dict[str, Any], *, confirmed: bool) -> SubmissionReceipt: ...
    def query(self, external_task_id: str) -> SubmissionReceipt: ...
    def download(self, external_task_id: str, output_dir: Path) -> tuple[Path, ...]: ...
