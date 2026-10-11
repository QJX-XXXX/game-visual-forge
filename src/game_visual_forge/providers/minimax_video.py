from __future__ import annotations

import base64
import hashlib
import os
import subprocess
import json
import re
import shutil
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

from game_visual_forge.contracts.provider import ExternalProvider
from game_visual_forge.contracts.video import VideoGenerationMode
from game_visual_forge.contracts.video_provider import VideoModelCatalogSnapshot, VideoModelProfile, VideoModelSupport, VideoProviderBackend
from game_visual_forge.providers.stdio import read_utf8_json, write_utf8_json


class JsonTransport(Protocol):
    def request(self, method: str, path: str, *, body: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]: ...

    def download(self, url: str, path: Path) -> Path: ...


@dataclass(frozen=True)
class MiniMaxSubmitRequest:
    endpoint: str
    body: dict[str, Any]


_H3_DURATIONS = tuple(range(4, 16))
_H3_RESOLUTIONS = ("768P", "2K")
_H3_RATIOS = ("adaptive", "21:9", "16:9", "4:3", "1:1", "3:4", "9:16")
_H3_CONCRETE_RATIOS = _H3_RATIOS[1:]


def _http_rejection(error: urllib.error.HTTPError) -> dict[str, Any]:
    try:
        payload = json.loads(error.read().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = {}
    details = payload.get("error") if isinstance(payload, dict) else None
    details = details if isinstance(details, dict) else {}
    message = str(details.get("message") or error.reason or "provider rejected request")
    message = re.sub(r"data:[^\s]+;base64,[^\s]+", "[redacted-media]", message, flags=re.IGNORECASE)[:500]
    code_match = re.search(r"\((\d+)\)\s*$", message)
    provider_code = details.get("code") or (code_match.group(1) if code_match else None)
    result: dict[str, Any] = {
        "schema_version": 1,
        "provider": "minimax",
        "backend": "api",
        "status": "rejected",
        "http_status": int(error.code),
        "error_type": str(details.get("type") or "http_error"),
        "message": message,
    }
    if provider_code is not None:
        result["error_code"] = str(provider_code)
    return result


def _transport_unknown(error: Exception) -> dict[str, Any]:
    message = re.sub(
        r"data:[^\s]+;base64,[^\s]+",
        "[redacted-media]",
        str(error) or "provider transport failed without details",
        flags=re.IGNORECASE,
    )[:500]
    return {
        "schema_version": 1,
        "provider": "minimax",
        "backend": "api",
        "status": "transport_unknown",
        "error_type": type(error).__name__,
        "message": message,
    }


def _media_item(media_type: str, url: str, role: str) -> dict[str, Any]:
    if not isinstance(url, str) or not url.strip():
        raise ValueError(f"{role} URL must not be empty")
    return {"type": media_type, media_type: {"url": url}, "role": role}


def _verified_png_data_uri(path_value: str, expected_sha256: str, *, root: Path | None = None) -> str:
    if not isinstance(path_value, str) or not path_value.strip():
        raise ValueError("first_frame_path must not be empty")
    if not isinstance(expected_sha256, str) or len(expected_sha256) != 64 or any(character not in "0123456789abcdef" for character in expected_sha256):
        raise ValueError("first_frame_sha256 must be a lowercase SHA-256 digest")
    relative = Path(path_value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("first_frame_path must be repository-relative")
    workspace = (root or Path.cwd()).resolve()
    path = (workspace / relative).resolve()
    if not path.is_relative_to(workspace):
        raise ValueError("first_frame_path must stay inside the repository")
    if path.suffix.lower() != ".png":
        raise ValueError("first_frame_path must resolve to a PNG")
    if not path.is_file():
        raise ValueError("first_frame_path does not exist")
    size = path.stat().st_size
    if size <= 0 or size > 30 * 1024 * 1024:
        raise ValueError("MiniMax first frame must be a non-empty PNG no larger than 30 MB")
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("first_frame_path does not contain a valid PNG signature")
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError("first frame SHA-256 does not match")
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


def _h3_profile() -> VideoModelProfile:
    return VideoModelProfile(
        1, ExternalProvider.MINIMAX, "MiniMax-H3", "v2", "/v2/video_generation",
        (VideoGenerationMode.T2V, VideoGenerationMode.I2V_FIRST, VideoGenerationMode.I2V_FIRST_TAIL, VideoGenerationMode.REFERENCE_TO_VIDEO),
        ("first_frame", "last_frame", "reference_image", "reference_video", "reference_audio"),
        _H3_DURATIONS, _H3_RESOLUTIONS, _H3_RATIOS, True,
        (VideoProviderBackend.API, VideoProviderBackend.CLI), "2026-08-09",
    )


def build_minimax_submit_request(
    *,
    model: str,
    mode: VideoGenerationMode,
    prompt: str,
    first_frame_url: str | None = None,
    last_frame_url: str | None = None,
    reference_image_urls: tuple[str, ...] = (),
    reference_video_urls: tuple[str, ...] = (),
    reference_audio_urls: tuple[str, ...] = (),
    duration: int = 6,
    resolution: str = "768P",
    ratio: str | None = None,
    aigc_watermark: bool = False,
) -> MiniMaxSubmitRequest:
    if model != "MiniMax-H3":
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        if first_frame_url is not None:
            content.append({"type": "image_url", "image_url": {"url": first_frame_url, "role": "first_frame"}})
        if last_frame_url is not None:
            content.append({"type": "image_url", "image_url": {"url": last_frame_url, "role": "last_frame"}})
        return MiniMaxSubmitRequest("/v1/video_generation", {"model": model, "prompt": prompt, "duration": duration, "content": content, "mode": mode.value})

    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("MiniMax-H3 prompt must not be empty")
    if len(prompt) > 7000:
        raise ValueError("MiniMax-H3 prompt must not exceed 7000 characters")
    if isinstance(duration, bool) or duration not in _H3_DURATIONS:
        raise ValueError("MiniMax-H3 duration must be an integer from 4 through 15")
    if resolution not in _H3_RESOLUTIONS:
        raise ValueError("MiniMax-H3 resolution must be 768P or 2K")
    if not isinstance(aigc_watermark, bool):
        raise TypeError("aigc_watermark must be a boolean")

    references = reference_image_urls + reference_video_urls + reference_audio_urls
    if (first_frame_url is not None or last_frame_url is not None) and references:
        raise ValueError("first/last frames cannot be mixed with multimodal references")

    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    if mode is VideoGenerationMode.T2V:
        if first_frame_url is not None or last_frame_url is not None or references:
            raise ValueError("MiniMax-H3 t2v accepts only a text prompt")
        resolved_ratio = ratio or "16:9"
        if resolved_ratio not in _H3_CONCRETE_RATIOS:
            raise ValueError("MiniMax-H3 t2v requires a concrete ratio")
    elif mode is VideoGenerationMode.I2V_FIRST:
        if first_frame_url is None:
            raise ValueError("MiniMax-H3 i2v-first requires first_frame_url")
        if last_frame_url is not None or references:
            raise ValueError("MiniMax-H3 i2v-first accepts only one first frame")
        content.append(_media_item("image_url", first_frame_url, "first_frame"))
        resolved_ratio = "adaptive"
    elif mode is VideoGenerationMode.I2V_FIRST_TAIL:
        if first_frame_url is None or last_frame_url is None:
            raise ValueError("MiniMax-H3 i2v-first-tail requires first_frame_url and last_frame_url")
        if references:
            raise ValueError("MiniMax-H3 first/last frames cannot be mixed with references")
        content.append(_media_item("image_url", first_frame_url, "first_frame"))
        content.append(_media_item("image_url", last_frame_url, "last_frame"))
        resolved_ratio = "adaptive"
    elif mode is VideoGenerationMode.REFERENCE_TO_VIDEO:
        if first_frame_url is not None or last_frame_url is not None:
            raise ValueError("MiniMax-H3 reference mode cannot use first/last frames")
        if not references:
            raise ValueError("MiniMax-H3 reference mode requires at least one reference URL")
        if len(reference_image_urls) > 9 or len(reference_video_urls) > 3 or len(reference_audio_urls) > 3 or len(references) > 12:
            raise ValueError("MiniMax-H3 reference count exceeds the documented limit")
        content.extend(_media_item("image_url", url, "reference_image") for url in reference_image_urls)
        content.extend(_media_item("video_url", url, "reference_video") for url in reference_video_urls)
        content.extend(_media_item("audio_url", url, "reference_audio") for url in reference_audio_urls)
        resolved_ratio = ratio or "adaptive"
        if resolved_ratio not in _H3_RATIOS:
            raise ValueError("MiniMax-H3 ratio is not supported")
    else:
        raise ValueError(f"MiniMax-H3 mode is not supported: {mode.value}")

    body = {
        "model": "MiniMax-H3",
        "content": content,
        "resolution": resolution,
        "duration": duration,
        "ratio": resolved_ratio,
        "aigc_watermark": aigc_watermark,
    }
    return MiniMaxSubmitRequest("/v2/video_generation", body)


def _prepared_submit_request(model: str, mode: VideoGenerationMode, parameters: dict[str, Any]) -> MiniMaxSubmitRequest:
    first_frame_url = parameters.get("first_frame_url")
    first_frame_path = parameters.get("first_frame_path")
    if first_frame_url is not None and first_frame_path is not None:
        raise ValueError("use either first_frame_url or first_frame_path, not both")
    if first_frame_path is not None:
        first_frame_url = _verified_png_data_uri(str(first_frame_path), parameters.get("first_frame_sha256"))
    return build_minimax_submit_request(
        model=model,
        mode=mode,
        prompt=str(parameters.get("prompt", "")),
        first_frame_url=first_frame_url,
        last_frame_url=parameters.get("last_frame_url"),
        reference_image_urls=tuple(str(item) for item in parameters.get("reference_image_urls", ())),
        reference_video_urls=tuple(str(item) for item in parameters.get("reference_video_urls", ())),
        reference_audio_urls=tuple(str(item) for item in parameters.get("reference_audio_urls", ())),
        duration=int(parameters.get("duration", 6)),
        resolution=str(parameters.get("resolution", "768P")),
        ratio=parameters.get("ratio"),
        aigc_watermark=parameters.get("aigc_watermark", False),
    )


class MiniMaxAdapter:
    provider = ExternalProvider.MINIMAX

    def __init__(self, *, region: str, transport: JsonTransport, cli_name: str = "mmx") -> None:
        if region not in {"global", "cn"}:
            raise ValueError("MiniMax region must be global or cn")
        self.region = region
        self.transport = transport
        self.cli_name = cli_name

    def _headers(self) -> dict[str, str]:
        key = os.environ.get("MINIMAX_API_KEY")
        if not key:
            raise RuntimeError("MINIMAX_API_KEY is not configured")
        return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    def preflight_api(self) -> dict[str, Any]:
        try:
            self._headers()
        except RuntimeError as error:
            return {"schema_version": 1, "provider": "minimax", "backend": "api", "available": False, "authenticated": False, "reason": str(error)}
        return {"schema_version": 1, "provider": "minimax", "backend": "api", "available": True, "authenticated": True, "region": self.region}

    def models(self) -> VideoModelCatalogSnapshot:
        payload = self.transport.request("GET", "/v1/models", headers=self._headers())
        discovered = payload.get("data", payload.get("models", []))
        model_ids = [item.get("id", item.get("model")) if isinstance(item, dict) else str(item) for item in discovered]
        profiles: list[VideoModelProfile | dict[str, Any]] = [_h3_profile()]
        for model_id in model_ids:
            if model_id == "MiniMax-H3":
                continue
            elif model_id:
                profiles.append({"model": str(model_id)})
        refreshed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        return VideoModelCatalogSnapshot.create(provider=self.provider, backend=VideoProviderBackend.API, region=self.region, refreshed_at=refreshed_at, adapter_version="1.1", models=tuple(profiles), source="minimax:/v1/models")

    def prepare(self, snapshot: VideoModelCatalogSnapshot, model: str, mode: VideoGenerationMode, parameters: dict[str, Any]) -> dict[str, Any]:
        profile = snapshot.model(model)
        if profile.support is VideoModelSupport.DISCOVERED_UNPROFILED:
            raise ValueError("model is discovered-unprofiled and cannot be submitted through the API")
        if mode not in profile.supported_modes:
            raise ValueError("model does not support requested generation mode")
        if model == "MiniMax-H3":
            _prepared_submit_request(model, mode, parameters)
        return {"schema_version": 1, "provider": "minimax", "backend": "api", "region": self.region, "model": model, "mode": mode.value, "parameters": dict(parameters), "endpoint": profile.endpoint}

    def estimate(self, prepared: dict[str, Any]) -> dict[str, Any]:
        return {"schema_version": 1, "provider": "minimax", "currency": None, "amount": None, "verified": False, "notice": "MiniMax estimate must be verified in the provider console before paid confirmation"}

    def submit(self, prepared: dict[str, Any]) -> dict[str, Any]:
        model = str(prepared["model"])
        parameters = dict(prepared.get("parameters", prepared))
        mode = VideoGenerationMode(prepared.get("mode", parameters.get("generation_mode", VideoGenerationMode.T2V.value)))
        request = _prepared_submit_request(model, mode, parameters)
        payload = self.transport.request("POST", request.endpoint, body=request.body, headers=self._headers())
        task_id = payload.get("task_id", payload.get("id"))
        if not task_id:
            raise RuntimeError("MiniMax did not return a task id")
        return {"schema_version": 1, "provider": "minimax", "backend": "api", "external_task_id": str(task_id), "status": str(payload.get("status", "submitted"))}

    def query(self, external_task_id: str) -> dict[str, Any]:
        task = self._query_task(external_task_id)
        receipt: dict[str, Any] = {
            "schema_version": 1,
            "provider": "minimax",
            "backend": "api",
            "external_task_id": external_task_id,
            "status": str(task.get("status", "unknown")),
        }
        for key in ("model", "resolution", "duration", "ratio", "task_type", "modality"):
            if task.get(key) is not None:
                receipt[key] = task[key]
        return receipt

    def _query_task(self, external_task_id: str) -> dict[str, Any]:
        if not external_task_id.strip():
            raise ValueError("MiniMax task id must not be empty")
        payload = self.transport.request("GET", f"/v2/query/video_generation/{external_task_id}", headers=self._headers())
        task = payload.get("task")
        if not isinstance(task, dict):
            raise RuntimeError("MiniMax did not return a task object")
        return task

    def download(self, external_task_id: str, output_path: Path) -> dict[str, Any]:
        task = self._query_task(external_task_id)
        status = str(task.get("status", "unknown"))
        if status != "succeeded":
            raise RuntimeError(f"MiniMax task is not succeeded: {status}")
        content = task.get("content")
        result_url = content.get("url") if isinstance(content, dict) else None
        if not isinstance(result_url, str) or not result_url.strip():
            raise RuntimeError("MiniMax succeeded task did not return a video URL")
        downloaded_path = Path(self.transport.download(result_url, output_path))
        if not downloaded_path.is_file() or downloaded_path.stat().st_size == 0:
            raise RuntimeError("MiniMax video download is empty")
        return {
            "schema_version": 1,
            "provider": "minimax",
            "backend": "api",
            "external_task_id": external_task_id,
            "status": "downloaded",
            "path": str(downloaded_path),
        }

    def preflight_cli(self, executable: Path, *, runner: Callable[[list[str]], tuple[int, str, str]] | None = None) -> dict[str, Any]:
        run = runner or self._run_cli
        code, stdout, stderr = run([str(executable), "--version"])
        if code != 0:
            return {"schema_version": 1, "provider": "minimax", "backend": "cli", "available": False, "authenticated": False, "reason": "mmx is unavailable"}
        return {"schema_version": 1, "provider": "minimax", "backend": "cli", "available": True, "authenticated": True, "version": stdout.strip(), "reason": None}

    @staticmethod
    def _run_cli(argv: list[str]) -> tuple[int, str, str]:
        result = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", shell=False, check=False)
        return result.returncode, result.stdout, result.stderr


def run_command(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    region = str(payload.get("region", "global"))
    default_base_url = "https://api.minimaxi.com" if region == "cn" else "https://api.minimax.io"
    transport = _UrllibTransport(str(payload.get("base_url") or default_base_url))
    adapter = MiniMaxAdapter(region=region, transport=transport)
    if command == "capabilities":
        return {"schema_version": 1, "provider": "minimax", "backend": payload.get("backend", "api"), "operations": ["capabilities", "models", "preflight", "estimate", "prepare", "submit", "query", "download"]}
    if command == "models":
        return adapter.models().to_dict()
    if command == "preflight":
        return adapter.preflight_api() if payload.get("backend", "api") == "api" else adapter.preflight_cli(Path(payload.get("executable", "mmx")))
    if command == "estimate":
        return adapter.estimate(payload)
    if command == "prepare":
        snapshot = VideoModelCatalogSnapshot.from_dict(payload["snapshot"])
        return adapter.prepare(snapshot, str(payload["model"]), VideoGenerationMode(payload["mode"]), dict(payload.get("parameters", {})))
    if command == "submit":
        return adapter.submit(payload)
    if command == "query":
        return adapter.query(str(payload["external_task_id"]))
    if command == "download":
        return adapter.download(str(payload["external_task_id"]), Path(str(payload["output_path"])))
    raise ValueError(f"unsupported MiniMax command: {command}")


class _UrllibTransport:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url or "https://api.minimax.io"

    def request(self, method: str, path: str, *, body: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
        request = urllib.request.Request(self.base_url.rstrip("/") + path, method=method, headers=headers or {})
        if body is not None:
            request.data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        with urllib.request.urlopen(request, timeout=120) as response:
            value = json.loads(response.read().decode("utf-8"))
        if not isinstance(value, dict):
            raise RuntimeError("MiniMax returned a non-object response")
        return value

    def download(self, url: str, path: Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        partial = destination.with_name(destination.name + ".part")
        try:
            with urllib.request.urlopen(url, timeout=120) as response, partial.open("wb") as target:
                shutil.copyfileobj(response, target)
            if partial.stat().st_size == 0:
                raise RuntimeError("MiniMax video download is empty")
            os.replace(partial, destination)
        finally:
            if partial.exists():
                partial.unlink()
        return destination


def main(
    argv: list[str] | None = None,
    input_stream: Any | None = None,
    output_stream: Any | None = None,
) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 1:
        raise SystemExit("usage: minimax_video.py <command>")
    payload = read_utf8_json(input_stream)
    try:
        result = run_command(arguments[0], payload)
    except urllib.error.HTTPError as error:
        if not 400 <= error.code < 500:
            result = _transport_unknown(error)
        else:
            result = _http_rejection(error)
    except Exception as error:
        if arguments[0] != "submit":
            raise
        result = _transport_unknown(error)
    write_utf8_json(result, output_stream)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
