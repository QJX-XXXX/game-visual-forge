from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Any, Callable, Mapping

from game_visual_forge.contracts.music_provider import MusicDownloadedFile, MusicHttpResponse, MusicProviderReceipt

STABLE_AUDIO_3_SUBMIT = "https://api.stability.ai/v2beta/audio/stable-audio/text-to-audio"
STABLE_AUDIO_3_RESULTS = "https://api.stability.ai/v2beta/audio/results/{}"
MusicHttpTransport = Callable[[str, str, Mapping[str, str], bytes | None], MusicHttpResponse]


def _body(response):
    try:
        return json.loads(response.body.decode("utf-8"))
    except Exception as exc:
        raise RuntimeError("Stable Audio returned invalid JSON") from exc


def _check_duration(duration):
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not 1 <= duration <= 380:
        raise ValueError("Stable Audio 3 duration must be between 1 and 380 seconds")


def preflight(payload):
    duration = payload.get("duration")
    try:
        _check_duration(duration)
    except ValueError as exc:
        return {"status": "unsupported", "reason": str(exc)}
    if payload.get("lyrics") or payload.get("vocal_policy") in {"vocals-allowed", "vocals-required"}:
        return {"status": "unsupported", "reason": "Stable Audio 3 route is instrumental-only for this skill"}
    if payload.get("output_format", "wav") not in {"wav", "mp3"}:
        return {"status": "unsupported", "reason": "output format must be wav or mp3"}
    return {"status": "ready", "model": "stable-audio-3", "duration_bounds": [1, 380], "vocal_policy": "instrumental"}


def _headers(payload, boundary):
    credential = payload.get("credential")
    if not credential:
        raise RuntimeError("Stable Audio credential is required at execution time")
    return {"Authorization": "Bearer " + str(credential), "Accept": "application/json", "Content-Type": "multipart/form-data; boundary=" + boundary}


def _multipart(fields, boundary):
    chunks = []
    for name, value in fields.items():
        chunks.append((f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n").encode("utf-8"))
    chunks.append((f"--{boundary}--\r\n").encode("ascii"))
    return b"".join(chunks)


def submit(payload: Mapping[str, Any], transport: MusicHttpTransport) -> MusicProviderReceipt:
    check = preflight(payload)
    if check["status"] != "ready":
        raise ValueError(check["reason"])
    body = {key: payload[key] for key in ("prompt", "model", "duration", "seed", "steps", "cfg_scale", "output_format") if key in payload}
    body["model"] = "stable-audio-3"
    boundary = "forge_music_" + uuid.uuid4().hex
    response = transport("POST", STABLE_AUDIO_3_SUBMIT, _headers(payload, boundary), _multipart(body, boundary))
    if response.status_code != 202:
        raise RuntimeError(f"Stable Audio submit failed with HTTP {response.status_code}")
    data = _body(response)
    task_id = data.get("id")
    if not isinstance(task_id, str) or not task_id:
        raise RuntimeError("Stable Audio submit response did not include an id")
    return MusicProviderReceipt("submitted", task_id)


def query(task_id: str, capability, transport: MusicHttpTransport) -> MusicProviderReceipt:
    if not isinstance(task_id, str) or not task_id:
        raise ValueError("task_id is required")
    headers = {"Accept": "application/json"}
    response = transport("GET", STABLE_AUDIO_3_RESULTS.format(task_id), headers, None)
    if response.status_code == 404:
        raise RuntimeError("Stable Audio task is missing or expired")
    if response.status_code == 202:
        return MusicProviderReceipt("running", task_id)
    if response.status_code != 200:
        raise RuntimeError(f"Stable Audio query failed with HTTP {response.status_code}")
    data = _body(response)
    status = str(data.get("status", "completed"))
    return MusicProviderReceipt("completed" if status in {"completed", "succeeded", "success"} else "running", task_id)


def download(task_id: str, capability, output_dir: Path, transport: MusicHttpTransport) -> tuple[MusicDownloadedFile, ...]:
    response = transport("GET", STABLE_AUDIO_3_RESULTS.format(task_id), {"Accept": "audio/wav, audio/mpeg"}, None)
    if response.status_code == 404:
        raise RuntimeError("Stable Audio task is missing or expired")
    if response.status_code != 200:
        raise RuntimeError(f"Stable Audio download failed with HTTP {response.status_code}")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = ".mp3" if response.headers.get("content-type", "").lower().find("mpeg") >= 0 else ".wav"
    final = output_dir / (task_id.replace("/", "_") + suffix)
    temporary = final.with_suffix(final.suffix + ".part")
    temporary.write_bytes(response.body)
    os.replace(temporary, final)
    return (MusicDownloadedFile(str(final), hashlib.sha256(response.body).hexdigest(), task_id),)
