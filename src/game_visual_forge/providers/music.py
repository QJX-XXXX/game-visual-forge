from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any

from game_visual_forge.contracts.music_provider import MusicAttemptStatus, MusicGenerationAttempt, MusicPaidConfirmation, MusicProviderReceipt, scan_safe
from game_visual_forge.contracts.serialization import dump_json, load_json
from game_visual_forge.contracts.music import music_hash


def _now(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("now must be UTC RFC3339")
    return value


def _parameters_hash(value):
    scan_safe(value)
    return music_hash(value)


def prepare_music_attempt(request, prompt, capability, parameters, *, now):
    _now(now)
    request_fingerprint = music_hash(request.to_dict())
    generation = music_hash({"request": request.to_dict(), "prompt": prompt.to_dict(), "capability": capability.to_dict(), "parameters": parameters})
    estimated = None if capability.credits_per_submission is None else capability.credits_per_submission * request.candidate_count
    return MusicGenerationAttempt(1, uuid.uuid4().hex, request_fingerprint, capability.provider, capability.model, capability.sha256, dict(parameters), _parameters_hash(parameters), generation, request.candidate_count, MusicAttemptStatus.PREPARED, capability.is_paid, now, now, estimated_credits=estimated)


def _write(path, attempt):
    dump_json(path, attempt.to_dict())
    return attempt


def _validate_confirmation(attempt, path):
    if not path or not path.exists():
        raise ValueError("paid confirmation is required")
    confirmation = MusicPaidConfirmation.from_dict(load_json(path))
    bindings = (("provider", confirmation.provider, attempt.provider), ("model", confirmation.model, attempt.model), ("capability_sha256", confirmation.capability_sha256, attempt.capability_sha256), ("generation_fingerprint", confirmation.generation_fingerprint, attempt.generation_fingerprint), ("parameters_sha256", confirmation.parameters_sha256, attempt.parameters_sha256), ("request_fingerprint", confirmation.request_fingerprint, attempt.request_fingerprint), ("submission_count", confirmation.submission_count, 1), ("expected_candidate_count", confirmation.expected_candidate_count, attempt.candidate_count), ("estimated_credits", confirmation.estimated_credits, attempt.estimated_credits))
    for name, actual, expected in bindings:
        if actual != expected:
            raise ValueError(f"paid confirmation binding mismatch: {name}")
    if confirmation.consumed:
        raise ValueError("paid confirmation has already been consumed")
    return confirmation


def begin_music_submission(attempt_path, confirmation_path, *, now):
    attempt = MusicGenerationAttempt.from_dict(load_json(attempt_path))
    if attempt.status is not MusicAttemptStatus.PREPARED:
        raise ValueError(f"attempt is not prepared: {attempt.status.value}")
    confirmation = None
    if attempt.is_paid:
        confirmation = _validate_confirmation(attempt, confirmation_path)
    updated = replace(attempt, status=MusicAttemptStatus.SUBMITTING, submission_count=attempt.submission_count + 1, updated_at=_now(now))
    _write(attempt_path, updated)
    if confirmation is not None:
        dump_json(confirmation_path, replace(confirmation, consumed=True).to_dict())
    return updated


def record_music_receipt(attempt_path, receipt, *, now):
    attempt = MusicGenerationAttempt.from_dict(load_json(attempt_path))
    if attempt.status not in {MusicAttemptStatus.SUBMITTING, MusicAttemptStatus.SUBMITTED, MusicAttemptStatus.RUNNING}:
        raise ValueError("receipt cannot update this attempt")
    status = MusicAttemptStatus.SUBMISSION_UNKNOWN if receipt.status == "submission_unknown" else MusicAttemptStatus(receipt.status)
    return _write(attempt_path, replace(attempt, status=status, external_task_id=receipt.external_task_id, returned_candidate_count=receipt.returned_candidate_count or len(receipt.candidate_ids), error_code=receipt.error_code, updated_at=_now(now)))


def _provider_call(executable, payload):
    result = subprocess.run([sys.executable, str(executable)], input=(json.dumps(payload) + "\n").encode("utf-8"), capture_output=True, timeout=60, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", "replace"))
    return json.loads(result.stdout.decode("utf-8"))


def submit_cloud_music_attempt(attempt_path, confirmation_path, executable, *, now):
    attempt = begin_music_submission(attempt_path, confirmation_path, now=now)
    try:
        value = _provider_call(executable, {"operation": "submit", "provider": attempt.provider.value, "model": attempt.model, "parameters": attempt.parameters, "candidate_count": attempt.candidate_count})
        return record_music_receipt(attempt_path, MusicProviderReceipt.from_dict(value), now=now)
    except Exception as exc:
        return _write(attempt_path, replace(attempt, status=MusicAttemptStatus.SUBMISSION_UNKNOWN, error_code=type(exc).__name__, updated_at=_now(now)))


def query_cloud_music_attempt(attempt_path, executable, *, now):
    attempt = MusicGenerationAttempt.from_dict(load_json(attempt_path))
    if not attempt.external_task_id:
        raise ValueError("cannot query without an external task ID; submission remains unknown")
    if attempt.status is MusicAttemptStatus.SUBMISSION_UNKNOWN:
        pass
    value = _provider_call(executable, {"operation": "query", "provider": attempt.provider.value, "external_task_id": attempt.external_task_id})
    return record_music_receipt(attempt_path, MusicProviderReceipt.from_dict(value), now=now)


def download_cloud_music_attempt(attempt_path, executable, output_dir, *, now):
    attempt = MusicGenerationAttempt.from_dict(load_json(attempt_path))
    if not attempt.external_task_id:
        raise ValueError("cannot download without an external task ID")
    value = _provider_call(executable, {"operation": "download", "provider": attempt.provider.value, "external_task_id": attempt.external_task_id, "output_dir": str(output_dir)})
    return record_music_receipt(attempt_path, MusicProviderReceipt.from_dict(value), now=now)
