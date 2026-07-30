from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from game_visual_forge.contracts import (
    CostEstimate,
    ExternalProvider,
    PaidConfirmation,
    ProviderCommand,
)
from game_visual_forge.errors import ErrorCode, ForgeError


_FORBIDDEN_KEYS = {"token", "cookie", "authorization", "api_key", "access_key", "secret", "signed_url", "base64"}
_SENSITIVE_OUTPUT = re.compile(r"data:[^\s]+;base64,|authorization\s*[:=]|api[_-]?key\s*[:=]|cookie\s*[:=]", re.IGNORECASE)


def _assert_safe(value: Any, path: str = "payload") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                raise ForgeError(ErrorCode.PROVIDER_UNAVAILABLE, "provider payload contains a forbidden secret field", recoverable=False, context={"path": path})
            _assert_safe(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _assert_safe(child, f"{path}[{index}]")
    elif isinstance(value, str) and _SENSITIVE_OUTPUT.search(value):
        raise ForgeError(ErrorCode.PROVIDER_UNAVAILABLE, "provider payload contains sensitive media or credentials", recoverable=False, context={"path": path})


def _argv(executable: Path, command: ProviderCommand) -> list[str]:
    if executable.suffix.lower() == ".py":
        return [sys.executable, str(executable), command.value]
    return [str(executable), command.value]


def _run_provider_command(
    executable: Path,
    command: ProviderCommand,
    payload: dict[str, Any],
    *,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    _assert_safe(payload)
    try:
        result = subprocess.run(
            _argv(executable, command),
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout_seconds,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ForgeError(ErrorCode.PROVIDER_UNAVAILABLE, f"provider command failed: {command.value}", recoverable=True, context={"command": command.value}) from error
    if result.returncode != 0 or _SENSITIVE_OUTPUT.search(result.stderr):
        raise ForgeError(ErrorCode.PROVIDER_UNAVAILABLE, f"provider command failed: {command.value}", recoverable=True, context={"command": command.value, "returncode": result.returncode})
    if _SENSITIVE_OUTPUT.search(result.stdout):
        raise ForgeError(ErrorCode.PROVIDER_UNAVAILABLE, "provider returned sensitive output", recoverable=False, context={"command": command.value})
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ForgeError(ErrorCode.PROVIDER_UNAVAILABLE, "provider returned invalid JSON", recoverable=True, context={"command": command.value}) from error
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ForgeError(ErrorCode.PROVIDER_UNAVAILABLE, "provider returned an invalid response", recoverable=True, context={"command": command.value})
    try:
        _assert_safe(value)
    except ForgeError as error:
        raise ForgeError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            "provider returned sensitive output",
            recoverable=False,
            context={"command": command.value},
        ) from error
    return value


def run_provider_command(
    executable: Path,
    command: ProviderCommand,
    payload: dict[str, Any],
    *,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    if command is ProviderCommand.SUBMIT:
        raise ForgeError(ErrorCode.CONFIRMATION_REQUIRED, "provider submit requires a bound confirmation", recoverable=True)
    return _run_provider_command(executable, command, payload, timeout_seconds=timeout_seconds)


def submit_provider_command(
    executable: Path,
    payload: dict[str, Any],
    confirmation: PaidConfirmation,
    *,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    estimate = CostEstimate.from_dict(payload["estimate"])
    if confirmation.consumed_at is None:
        raise ForgeError(ErrorCode.CONFIRMATION_REQUIRED, "confirmation must be consumed and persisted before submit", recoverable=True)
    confirmation.assert_binding_matches(
        attempt_id=payload["attempt_id"],
        provider=ExternalProvider(payload["provider"]),
        model=payload["model"],
        parameters=payload["parameters"],
        quantity=payload["quantity"],
        estimate=estimate,
        request_fingerprint=payload["request_fingerprint"],
    )
    return _run_provider_command(executable, ProviderCommand.SUBMIT, payload, timeout_seconds=timeout_seconds)
