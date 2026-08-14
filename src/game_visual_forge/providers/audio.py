from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from game_visual_forge.contracts.audio import AudioRequest
from game_visual_forge.contracts.audio_provider import (
    AudioAttemptStatus,
    AudioCandidateRecord,
    AudioGenerationAttempt,
    AudioGenerationResult,
    AudioProviderPreflight,
)
from game_visual_forge.contracts.provider import ProviderCommand
from game_visual_forge.contracts.serialization import dump_json
from game_visual_forge.errors import ErrorCode, ForgeError
from game_visual_forge.jobs.fingerprints import fingerprint_request
from game_visual_forge.providers.stdio import run_utf8_json_process


def _argv(executable: Path, command: ProviderCommand) -> list[str]:
    if executable.suffix.lower() == ".py":
        return [sys.executable, str(executable), command.value]
    return [str(executable), command.value]


def _run(executable: Path, command: ProviderCommand, payload: dict[str, Any], *, timeout_seconds: int = 120) -> dict[str, Any]:
    try:
        result = run_utf8_json_process(_argv(executable, command), payload, timeout_seconds=timeout_seconds)
    except subprocess.TimeoutExpired as error:
        raise ForgeError(ErrorCode.PROVIDER_UNAVAILABLE, "audio provider command timed out", recoverable=True, context={"command": command.value, "outcome": "generation_unknown"}) from error
    except UnicodeDecodeError as error:
        raise ForgeError(ErrorCode.PROVIDER_UNAVAILABLE, "audio provider returned invalid UTF-8", recoverable=True, context={"command": command.value, "outcome": "generation_unknown"}) from error
    except OSError as error:
        raise ForgeError(ErrorCode.PROVIDER_UNAVAILABLE, "audio provider executable is unavailable", recoverable=True, context={"command": command.value}) from error
    if result.returncode != 0:
        raise ForgeError(ErrorCode.PROVIDER_UNAVAILABLE, "audio provider command failed", recoverable=True, context={"command": command.value, "returncode": result.returncode, "stderr": result.stderr[-1000:]})
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ForgeError(ErrorCode.PROVIDER_UNAVAILABLE, "audio provider returned invalid JSON", recoverable=True, context={"command": command.value, "outcome": "generation_unknown"}) from error
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ForgeError(ErrorCode.PROVIDER_UNAVAILABLE, "audio provider returned an invalid response", recoverable=True, context={"command": command.value})
    return value


def run_audio_provider_models(executable: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return _run(executable, ProviderCommand.MODELS, payload)


def run_audio_provider_preflight(executable: Path, payload: dict[str, Any]) -> AudioProviderPreflight:
    return AudioProviderPreflight.from_dict(_run(executable, ProviderCommand.PREFLIGHT, payload))


def _persist_attempt(attempt_path: Path, attempt: AudioGenerationAttempt) -> None:
    attempt_path.parent.mkdir(parents=True, exist_ok=True)
    dump_json(attempt_path, attempt.to_dict())


def generate_audio_candidates(
    request: AudioRequest,
    attempt_path: Path,
    executable: Path,
    output_dir: Path,
    source: Any | None,
    now: str,
) -> AudioGenerationResult:
    fingerprint = fingerprint_request(request.to_dict())
    output_dir.mkdir(parents=True, exist_ok=True)
    attempt_root = attempt_path if attempt_path.suffix == "" else attempt_path.parent
    attempt_root.mkdir(parents=True, exist_ok=True)
    candidates: list[AudioCandidateRecord] = []
    attempt_paths: list[str] = []
    seed_base = int(fingerprint[:8], 16)
    source_path = getattr(source, "path", None) if source is not None else None
    for index in range(request.candidate_count):
        candidate_id = f"candidate-{index + 1:02d}"
        seed = (seed_base + index) % (2**31)
        raw_relative = f"raw/{candidate_id}.wav"
        output_path = output_dir / raw_relative
        attempt_file = attempt_root / f"{candidate_id}.json"
        parameters = {
            "prompt": request.prompt,
            "duration_seconds": request.duration_seconds,
            "source_path": source_path,
            "edit_start_seconds": request.edit_start_seconds,
            "edit_end_seconds": request.edit_end_seconds,
        }
        attempt = AudioGenerationAttempt(1, candidate_id, fingerprint, "small-sfx", request.mode, seed, parameters, AudioAttemptStatus.PREPARED, now, now)
        _persist_attempt(attempt_file, attempt)
        attempt_paths.append(str(attempt_file))
        attempt = attempt.replace(status=AudioAttemptStatus.RUNNING, updated_at=now)
        _persist_attempt(attempt_file, attempt)
        payload = {
            "schema_version": 1,
            "provider": "stable-audio-local",
            "model_id": "small-sfx",
            "mode": request.mode.value,
            "prompt": request.prompt,
            "duration_seconds": request.duration_seconds,
            "seed": seed,
            "output_path": str(output_path),
            "source_path": source_path,
            "redraw_strength": request.redraw_strength,
            "edit_start_seconds": request.edit_start_seconds,
            "edit_end_seconds": request.edit_end_seconds,
        }
        try:
            response = _run(executable, ProviderCommand.GENERATE, payload)
            if not output_path.is_file() or output_path.stat().st_size <= 44:
                raise ForgeError(ErrorCode.PROVIDER_UNAVAILABLE, "audio provider produced no usable output", recoverable=True, context={"outcome": "generation_unknown"})
            digest = hashlib.sha256(output_path.read_bytes()).hexdigest()
            completed = attempt.replace(status=AudioAttemptStatus.COMPLETED, updated_at=now, output_path=raw_relative, output_sha256=digest)
            _persist_attempt(attempt_file, completed)
            candidates.append(AudioCandidateRecord(1, candidate_id, candidate_id, seed, raw_relative, digest))
        except ForgeError as error:
            unknown = error.context.get("outcome") == "generation_unknown"
            status = AudioAttemptStatus.GENERATION_UNKNOWN if unknown else AudioAttemptStatus.FAILED
            failed = attempt.replace(status=status, updated_at=now, error_code=("generation_unknown" if unknown else "provider_failed"))
            _persist_attempt(attempt_file, failed)
    return AudioGenerationResult(1, fingerprint, request.mode, tuple(candidates), tuple(attempt_paths))
