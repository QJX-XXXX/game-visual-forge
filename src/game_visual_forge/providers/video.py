from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from game_visual_forge.contracts.serialization import dump_json, load_json
from game_visual_forge.contracts.video_provider import VideoAttemptStatus, VideoGenerationAttempt, VideoPaidConfirmation
from game_visual_forge.contracts.video import VideoGenerationMode
from game_visual_forge.contracts.provider import ProviderCommand
from game_visual_forge.errors import ErrorCode, ForgeError
from game_visual_forge.processing.video_probe import sha256_file
from game_visual_forge.providers.cli import _assert_safe
from game_visual_forge.providers.stdio import run_utf8_json_process


def _argv(executable: Path, command: ProviderCommand) -> list[str]:
    return [sys.executable, str(executable), command.value] if executable.suffix.lower() == ".py" else [str(executable), command.value]


def _run(executable: Path, command: ProviderCommand, payload: dict[str, Any], *, timeout_seconds: int = 30) -> dict[str, Any]:
    _assert_safe(payload)
    try:
        result = run_utf8_json_process(_argv(executable, command), payload, timeout_seconds=timeout_seconds)
    except subprocess.TimeoutExpired as error:
        raise ForgeError(ErrorCode.SUBMISSION_UNKNOWN if command is ProviderCommand.SUBMIT else ErrorCode.PROVIDER_UNAVAILABLE, "provider command outcome is unknown" if command is ProviderCommand.SUBMIT else "provider command timed out", recoverable=True, context={"command": command.value}) from error
    except OSError as error:
        raise ForgeError(ErrorCode.PROVIDER_UNAVAILABLE, "provider command could not start", recoverable=True, context={"command": command.value}) from error
    except UnicodeDecodeError as error:
        if command is ProviderCommand.SUBMIT:
            raise ForgeError(ErrorCode.SUBMISSION_UNKNOWN, "provider submit outcome is unknown", recoverable=True, context={"command": command.value}) from error
        raise ForgeError(ErrorCode.PROVIDER_UNAVAILABLE, "provider returned invalid UTF-8", recoverable=True, context={"command": command.value}) from error
    if result.returncode != 0:
        if command is ProviderCommand.SUBMIT:
            raise ForgeError(ErrorCode.SUBMISSION_UNKNOWN, "provider submit outcome is unknown", recoverable=True, context={"command": command.value})
        raise ForgeError(ErrorCode.PROVIDER_UNAVAILABLE, "provider command failed", recoverable=True, context={"command": command.value})
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        if command is ProviderCommand.SUBMIT:
            raise ForgeError(ErrorCode.SUBMISSION_UNKNOWN, "provider submit outcome is unknown", recoverable=True, context={"command": command.value}) from error
        raise ForgeError(ErrorCode.PROVIDER_UNAVAILABLE, "provider returned invalid JSON", recoverable=True, context={"command": command.value}) from error
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ForgeError(ErrorCode.PROVIDER_UNAVAILABLE, "provider returned an invalid response", recoverable=True, context={"command": command.value})
    _assert_safe(value)
    return value


def _attempt_generation_binding(attempt: VideoGenerationAttempt) -> tuple[VideoGenerationMode, tuple[str, ...]]:
    mode = VideoGenerationMode(str(attempt.parameters.get("generation_mode", VideoGenerationMode.T2V.value)))
    reference_sha256 = tuple(str(item) for item in attempt.parameters.get("reference_sha256", []))
    return mode, reference_sha256


def submit_video_attempt(attempt_path: Path, confirmation_path: Path, executable: Path, *, now: str) -> VideoGenerationAttempt:
    attempt = VideoGenerationAttempt.from_dict(load_json(attempt_path))
    if attempt.status not in {VideoAttemptStatus.PREPARED, VideoAttemptStatus.AWAITING_CONFIRMATION}:
        raise ValueError("only a prepared attempt can submit; use query for submission_unknown")
    confirmation = VideoPaidConfirmation.from_dict(load_json(confirmation_path))
    mode, reference_sha256 = _attempt_generation_binding(attempt)
    values = {"attempt_id": attempt.attempt_id, "provider": attempt.provider, "backend": attempt.backend, "region": attempt.region, "model": attempt.model, "model_snapshot_sha256": attempt.model_snapshot_sha256, "mode": mode, "parameters": attempt.parameters, "reference_sha256": reference_sha256, "quantity": 1, "estimate": confirmation.estimate, "request_fingerprint": attempt.request_fingerprint}
    authorized = confirmation.authorize_attempt(now=now, **values)
    dump_json(confirmation_path, authorized.to_dict())
    submitting = attempt.replace(status=VideoAttemptStatus.SUBMITTING, updated_at=now, confirmation_binding_fingerprint=authorized.binding_fingerprint)
    dump_json(attempt_path, submitting.to_dict())
    payload = {"schema_version": 1, "attempt_id": submitting.attempt_id, "provider": submitting.provider.value, "backend": submitting.backend.value, "region": submitting.region, "model": submitting.model, "mode": mode.value, "parameters": submitting.parameters, "request_fingerprint": submitting.request_fingerprint}
    try:
        receipt = _run(executable, ProviderCommand.SUBMIT, payload)
    except ForgeError as error:
        if error.code is ErrorCode.SUBMISSION_UNKNOWN:
            unknown = submitting.replace(status=VideoAttemptStatus.SUBMISSION_UNKNOWN, updated_at=now, error_code=error.code.value)
            dump_json(attempt_path, unknown.to_dict())
            return unknown
        raise
    if receipt.get("status") == "rejected":
        error_code = str(receipt.get("error_code") or f"http_{receipt.get('http_status', '4xx')}")
        rejection_path = attempt_path.with_name(f"{attempt_path.stem}-provider-rejection.json")
        dump_json(rejection_path, receipt)
        failed = submitting.replace(status=VideoAttemptStatus.FAILED, updated_at=now, error_code=error_code)
        dump_json(attempt_path, failed.to_dict())
        return failed
    if receipt.get("status") == "transport_unknown":
        diagnostic_path = attempt_path.with_name(f"{attempt_path.stem}-provider-diagnostic.json")
        dump_json(diagnostic_path, receipt)
        unknown = submitting.replace(status=VideoAttemptStatus.SUBMISSION_UNKNOWN, updated_at=now, error_code=ErrorCode.SUBMISSION_UNKNOWN.value)
        dump_json(attempt_path, unknown.to_dict())
        return unknown
    task_id = receipt.get("external_task_id")
    if not task_id:
        unknown = submitting.replace(status=VideoAttemptStatus.SUBMISSION_UNKNOWN, updated_at=now, error_code=ErrorCode.SUBMISSION_UNKNOWN.value)
        dump_json(attempt_path, unknown.to_dict())
        return unknown
    completed = submitting.replace(status=VideoAttemptStatus.SUBMITTED, updated_at=now, external_task_id=str(task_id), error_code=None)
    dump_json(attempt_path, completed.to_dict())
    return completed


def query_video_attempt(attempt_path: Path, executable: Path, *, now: str) -> VideoGenerationAttempt:
    attempt = VideoGenerationAttempt.from_dict(load_json(attempt_path))
    if attempt.external_task_id is None:
        raise ValueError("query requires an existing external task id")
    payload = {"schema_version": 1, "provider": attempt.provider.value, "backend": attempt.backend.value, "region": attempt.region, "external_task_id": attempt.external_task_id}
    receipt = _run(executable, ProviderCommand.QUERY, payload)
    provider_status = str(receipt.get("status", "unknown"))
    if provider_status in {"completed", "succeeded", "success"}:
        status = VideoAttemptStatus.COMPLETED
    elif provider_status == "failed":
        status = VideoAttemptStatus.FAILED
    elif provider_status in {"cancelled", "canceled"}:
        status = VideoAttemptStatus.CANCELLED
    else:
        status = VideoAttemptStatus.RUNNING
    result = attempt.replace(status=status, updated_at=now)
    dump_json(attempt_path, result.to_dict())
    return result


def download_video_attempt(attempt_path: Path, executable: Path, output_dir: Path, *, now: str) -> VideoGenerationAttempt:
    attempt = VideoGenerationAttempt.from_dict(load_json(attempt_path))
    if attempt.external_task_id is None:
        raise ValueError("download requires an existing external task id")
    output_dir.mkdir(parents=True, exist_ok=True)
    temporary = output_dir / ".video-download.tmp"
    target = output_dir / "video.mp4"
    payload = {"schema_version": 1, "provider": attempt.provider.value, "backend": attempt.backend.value, "region": attempt.region, "external_task_id": attempt.external_task_id, "output_path": str(temporary)}
    receipt = _run(executable, ProviderCommand.DOWNLOAD, payload)
    provider_path = Path(str(receipt.get("path", temporary)))
    if not provider_path.is_file() or provider_path.stat().st_size == 0:
        raise ValueError("provider download is empty")
    os.replace(provider_path, target)
    relative = target.relative_to(attempt_path.parent.resolve()).as_posix()
    result = attempt.replace(status=VideoAttemptStatus.DOWNLOADED, updated_at=now, downloaded_path=relative, downloaded_sha256=sha256_file(target))
    dump_json(attempt_path, result.to_dict())
    return result
