from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any

from .provider import CostEstimate, ExternalProvider


_DIGEST = re.compile(r"[0-9a-f]{64}")
_SECRET_KEYS = {"token", "cookie", "authorization", "api_key", "access_key", "secret", "signed_url", "base64"}


def _timestamp(value: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("confirmed_at must be a UTC RFC 3339 timestamp")
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ValueError("confirmed_at must be a UTC RFC 3339 timestamp") from error
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


def _binding_payload(
    *,
    attempt_id: str,
    provider: ExternalProvider,
    model: str,
    parameters: dict[str, Any],
    quantity: int,
    estimate: CostEstimate,
    request_fingerprint: str,
) -> dict[str, Any]:
    _scan_safe(parameters)
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    if not _DIGEST.fullmatch(request_fingerprint):
        raise ValueError("request_fingerprint must be a SHA-256 hex digest")
    if not estimate.verified:
        raise ValueError("cost estimate must be verified")
    return {
        "attempt_id": attempt_id,
        "provider": provider.value,
        "model": model,
        "parameters": parameters,
        "quantity": quantity,
        "estimate": estimate.to_dict(),
        "request_fingerprint": request_fingerprint,
    }


def _fingerprint(value: dict[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class PaidConfirmation:
    schema_version: int
    attempt_id: str
    provider: ExternalProvider
    model: str
    parameters: dict[str, Any]
    quantity: int
    estimate: CostEstimate
    request_fingerprint: str
    confirmed_at: str
    binding_fingerprint: str
    consumed_at: str | None = None

    @classmethod
    def create(
        cls,
        *,
        attempt_id: str,
        provider: ExternalProvider,
        model: str,
        parameters: dict[str, Any],
        quantity: int,
        estimate: CostEstimate,
        request_fingerprint: str,
        confirmed_at: str,
    ) -> "PaidConfirmation":
        if not isinstance(attempt_id, str) or not attempt_id.strip():
            raise ValueError("attempt_id must not be empty")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must not be empty")
        confirmed_at = _timestamp(confirmed_at)
        binding = _binding_payload(
            attempt_id=attempt_id,
            provider=provider,
            model=model,
            parameters=parameters,
            quantity=quantity,
            estimate=estimate,
            request_fingerprint=request_fingerprint,
        )
        return cls(1, attempt_id, provider, model, parameters, quantity, estimate, request_fingerprint, confirmed_at, _fingerprint(binding))

    def _assert_binding(
        self,
        *,
        attempt_id: str,
        provider: ExternalProvider,
        model: str,
        parameters: dict[str, Any],
        quantity: int,
        estimate: CostEstimate,
        request_fingerprint: str,
    ) -> None:
        expected = _fingerprint(_binding_payload(
            attempt_id=attempt_id,
            provider=provider,
            model=model,
            parameters=parameters,
            quantity=quantity,
            estimate=estimate,
            request_fingerprint=request_fingerprint,
        ))
        if expected != self.binding_fingerprint:
            raise ValueError("confirmation binding does not match")

    def assert_authorizes(self, **kwargs: Any) -> None:
        if self.consumed_at is not None:
            raise ValueError("confirmation already consumed")
        self._assert_binding(**kwargs)

    def assert_binding_matches(self, **kwargs: Any) -> None:
        self._assert_binding(**kwargs)

    def authorize_attempt(self, *, now: str, **kwargs: Any) -> "PaidConfirmation":
        self.assert_authorizes(**kwargs)
        return replace(self, consumed_at=_timestamp(now))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "attempt_id": self.attempt_id,
            "provider": self.provider.value,
            "model": self.model,
            "parameters": self.parameters,
            "quantity": self.quantity,
            "estimate": self.estimate.to_dict(),
            "request_fingerprint": self.request_fingerprint,
            "confirmed_at": self.confirmed_at,
            "binding_fingerprint": self.binding_fingerprint,
            "consumed_at": self.consumed_at,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "PaidConfirmation":
        if not isinstance(value, dict):
            raise TypeError("PaidConfirmation payload must be an object")
        estimate = CostEstimate.from_dict(value["estimate"])
        result = cls(
            schema_version=value["schema_version"],
            attempt_id=value["attempt_id"],
            provider=ExternalProvider(value["provider"]),
            model=value["model"],
            parameters=value["parameters"],
            quantity=value["quantity"],
            estimate=estimate,
            request_fingerprint=value["request_fingerprint"],
            confirmed_at=value["confirmed_at"],
            binding_fingerprint=value["binding_fingerprint"],
            consumed_at=value.get("consumed_at"),
        )
        if result.schema_version != 1 or not _DIGEST.fullmatch(result.binding_fingerprint):
            raise ValueError("invalid PaidConfirmation schema or binding")
        _timestamp(result.confirmed_at)
        if result.consumed_at is not None:
            _timestamp(result.consumed_at)
        result._assert_binding(
            attempt_id=result.attempt_id,
            provider=result.provider,
            model=result.model,
            parameters=result.parameters,
            quantity=result.quantity,
            estimate=result.estimate,
            request_fingerprint=result.request_fingerprint,
        )
        return result
