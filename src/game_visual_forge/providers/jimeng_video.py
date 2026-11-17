from __future__ import annotations

import hashlib
import hmac
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

from game_visual_forge.contracts.provider import ExternalProvider
from game_visual_forge.contracts.video import VideoGenerationMode
from game_visual_forge.contracts.video_provider import (
    VideoModelCatalogSnapshot,
    VideoModelProfile,
    VideoModelSupport,
    VideoProviderBackend,
)
from game_visual_forge.providers.stdio import read_utf8_json, write_utf8_json


VOLCENGINE_BASE_URL = "https://visual.volcengineapi.com"
VOLCENGINE_REGION = "cn-north-1"
VOLCENGINE_SERVICE = "cv"
VOLCENGINE_API_VERSION = "2022-08-31"
VOLCENGINE_SUBMIT_ACTION = "CVSync2AsyncSubmitTask"
VOLCENGINE_QUERY_ACTION = "CVSync2AsyncGetResult"

JIMENG_PRO_MODEL = "ti2v_v30_pro_jimeng"
JIMENG_T2V_MODEL = "jimeng_t2v_v30"
JIMENG_I2V_FIRST_MODEL = "jimeng_i2v_first_v30_1080"
JIMENG_I2V_FIRST_TAIL_MODEL = "jimeng_i2v_first_tail_v30_1080"


class JsonTransport(Protocol):
    def request(self, method: str, path: str, *, body: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]: ...

    def download(self, url: str, path: Path) -> Path: ...


@dataclass(frozen=True)
class SignedRequest:
    authorization: str
    headers: dict[str, str]


def _json_bytes(body: dict[str, Any]) -> bytes:
    return json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _normalized_now(now: str | None) -> str:
    if now:
        if len(now) == 16 and now.endswith("Z") and "T" in now:
            return now
        try:
            parsed = datetime.fromisoformat(now.replace("Z", "+00:00")).astimezone(timezone.utc)
            return parsed.strftime("%Y%m%dT%H%M%SZ")
        except ValueError:
            pass
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _request_url(url: str) -> urllib.parse.SplitResult:
    if "://" not in url:
        url = VOLCENGINE_BASE_URL.rstrip("/") + (url if url.startswith("/") else "/" + url)
    parsed = urllib.parse.urlsplit(url)
    if not parsed.netloc:
        raise ValueError("Volcengine request URL must include a host")
    return parsed


def _canonical_query(query: str) -> str:
    pairs = urllib.parse.parse_qsl(query, keep_blank_values=True)
    return "&".join(
        f"{urllib.parse.quote(key, safe='-_.~')}={urllib.parse.quote(value, safe='-_.~')}"
        for key, value in sorted(pairs)
    )


def _canonical_uri(path: str) -> str:
    return urllib.parse.quote(path or "/", safe="/-_.~")


def _hmac(key: bytes, value: str) -> bytes:
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).digest()


def sign_volcengine_request(
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    body: dict[str, Any],
    access_key: str,
    secret_key: str,
    now: str,
    region: str = VOLCENGINE_REGION,
    service: str = VOLCENGINE_SERVICE,
) -> SignedRequest:
    """Create the Volcengine public HMAC-SHA256 V4 request signature."""
    parsed = _request_url(url)
    request_headers = {str(key): str(value) for key, value in headers.items()}
    request_headers["Host"] = parsed.netloc
    format_date = _normalized_now(now)
    body_bytes = _json_bytes(body)
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    request_headers["X-Date"] = format_date
    request_headers["X-Content-Sha256"] = body_hash

    signed_values: dict[str, str] = {}
    for key, value in request_headers.items():
        normalized = key.lower()
        if normalized in {"content-type", "content-md5", "host"} or normalized.startswith("x-"):
            signed_values[normalized] = value.strip()
    signed_headers = ";".join(sorted(signed_values))
    canonical_headers = "".join(f"{key}:{signed_values[key]}\n" for key in sorted(signed_values))
    canonical_request = "\n".join(
        (
            method.upper(),
            _canonical_uri(parsed.path),
            _canonical_query(parsed.query),
            canonical_headers,
            signed_headers,
            body_hash,
        )
    )
    short_date = format_date[:8]
    credential_scope = f"{short_date}/{region}/{service}/request"
    string_to_sign = "\n".join(
        (
            "HMAC-SHA256",
            format_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        )
    )
    signing_key = _hmac(_hmac(_hmac(_hmac(secret_key.encode("utf-8"), short_date), region), service), "request")
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    authorization = f"HMAC-SHA256 Credential={access_key}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"
    request_headers["Authorization"] = authorization
    return SignedRequest(authorization, request_headers)


def _action_path(action: str) -> str:
    query = urllib.parse.urlencode({"Action": action, "Version": VOLCENGINE_API_VERSION})
    return "/?" + query


def _string_list(parameters: dict[str, Any], name: str) -> tuple[str, ...]:
    value = parameters.get(name, ())
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{name} must be a list of URLs")
    return tuple(str(item) for item in value)


def _model_for_mode(mode: VideoGenerationMode, parameters: dict[str, Any]) -> str:
    explicit = parameters.get("model") or parameters.get("req_key")
    if explicit and str(explicit) not in {"jimeng", "jimeng-api"}:
        return str(explicit)
    if mode in {VideoGenerationMode.T2V, VideoGenerationMode.I2V_FIRST}:
        return JIMENG_PRO_MODEL
    if mode is VideoGenerationMode.I2V_FIRST_TAIL:
        return JIMENG_I2V_FIRST_TAIL_MODEL
    raise ValueError(f"current Jimeng API does not support {mode.value}")


def build_jimeng_submit_body(*, model: str, mode: VideoGenerationMode, parameters: dict[str, Any]) -> dict[str, Any]:
    prompt = parameters.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("Jimeng prompt must not be empty")
    if len(prompt) > 800:
        raise ValueError("Jimeng prompt must not exceed 800 characters")

    images = _string_list(parameters, "image_urls")
    base64_images = _string_list(parameters, "binary_data_base64")
    if images and base64_images:
        raise ValueError("image_urls and binary_data_base64 are mutually exclusive")
    if base64_images:
        raise ValueError("binary_data_base64 is not accepted through the persisted provider payload")

    if model == JIMENG_PRO_MODEL:
        supported_modes = {VideoGenerationMode.T2V, VideoGenerationMode.I2V_FIRST}
    elif model == JIMENG_T2V_MODEL:
        supported_modes = {VideoGenerationMode.T2V}
    elif model == JIMENG_I2V_FIRST_MODEL:
        supported_modes = {VideoGenerationMode.I2V_FIRST}
    elif model == JIMENG_I2V_FIRST_TAIL_MODEL:
        supported_modes = {VideoGenerationMode.I2V_FIRST_TAIL}
    else:
        raise ValueError(f"unsupported Jimeng model: {model}")
    if mode not in supported_modes:
        raise ValueError(f"{model} does not support {mode.value}")

    if mode is VideoGenerationMode.T2V and images:
        raise ValueError("Jimeng text-to-video does not accept image_urls")
    required_images = 0 if mode is VideoGenerationMode.T2V else 1 if mode is VideoGenerationMode.I2V_FIRST else 2
    if len(images) != required_images:
        raise ValueError(f"{model} requires {required_images} image URL(s) for {mode.value}")

    seed = parameters.get("seed", -1)
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("Jimeng seed must be an integer")
    frames = parameters.get("frames", 121)
    if isinstance(frames, bool) or frames not in {121, 241}:
        raise ValueError("Jimeng frames must be 121 or 241")

    body: dict[str, Any] = {"req_key": model, "prompt": prompt, "seed": seed, "frames": frames}
    if images:
        body["image_urls"] = list(images)
    aspect_ratio = parameters.get("aspect_ratio")
    if aspect_ratio is not None:
        if aspect_ratio not in {"16:9", "4:3", "1:1", "3:4", "9:16", "21:9"}:
            raise ValueError("Jimeng aspect_ratio is not supported")
        if mode is not VideoGenerationMode.T2V:
            raise ValueError("Jimeng aspect_ratio is only supported for text-to-video")
        body["aspect_ratio"] = aspect_ratio
    return body


def _profile(
    model: str,
    modes: tuple[VideoGenerationMode, ...],
    resolution: str,
    roles: tuple[str, ...],
    support: VideoModelSupport = VideoModelSupport.PROFILED,
) -> VideoModelProfile:
    return VideoModelProfile(
        1,
        ExternalProvider.JIMENG,
        model,
        "cv-2022-08-31",
        "/?Action=CVSync2AsyncSubmitTask&Version=2022-08-31",
        modes,
        roles,
        (5, 10),
        (resolution,),
        ("21:9", "16:9", "4:3", "1:1", "3:4", "9:16"),
        False,
        (VideoProviderBackend.API,),
        "2026-11-17",
        support,
    )


class JimengAdapter:
    provider = ExternalProvider.JIMENG

    def __init__(self, *, transport: JsonTransport) -> None:
        self.transport = transport

    def _credentials(self) -> tuple[str, str]:
        access_key = os.environ.get("JIMENG_ACCESS_KEY")
        secret_key = os.environ.get("JIMENG_SECRET_KEY")
        if not access_key or not secret_key:
            raise RuntimeError("JIMENG_ACCESS_KEY and JIMENG_SECRET_KEY are required")
        return access_key, secret_key

    def _headers(self, path: str, body: dict[str, Any]) -> dict[str, str]:
        access_key, secret_key = self._credentials()
        signed = sign_volcengine_request(
            method="POST",
            url=path,
            headers={"Content-Type": "application/json"},
            body=body,
            access_key=access_key,
            secret_key=secret_key,
            now=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        )
        signed.headers["Region"] = VOLCENGINE_REGION
        signed.headers["Service"] = VOLCENGINE_SERVICE
        return signed.headers

    def preflight_api(self) -> dict[str, Any]:
        try:
            self._credentials()
        except RuntimeError as error:
            return {"schema_version": 1, "provider": "jimeng", "backend": "api", "available": False, "authenticated": False, "reason": str(error)}
        return {
            "schema_version": 1,
            "provider": "jimeng",
            "backend": "api",
            "available": True,
            "authenticated": True,
            "region": VOLCENGINE_REGION,
            "service": VOLCENGINE_SERVICE,
            "api_version": VOLCENGINE_API_VERSION,
        }

    def estimate(self, parameters: dict[str, Any]) -> dict[str, Any]:
        return {"schema_version": 1, "provider": "jimeng", "currency": None, "amount": None, "verified": False, "notice": "Jimeng estimate must be verified in the provider console before paid confirmation"}

    def models(self) -> VideoModelCatalogSnapshot:
        models = (
            _profile(JIMENG_PRO_MODEL, (VideoGenerationMode.T2V, VideoGenerationMode.I2V_FIRST), "1080P", ("first_frame",)),
            _profile(JIMENG_T2V_MODEL, (VideoGenerationMode.T2V,), "720P", ()),
            _profile(JIMENG_I2V_FIRST_MODEL, (VideoGenerationMode.I2V_FIRST,), "1080P", ("first_frame",)),
            _profile(JIMENG_I2V_FIRST_TAIL_MODEL, (VideoGenerationMode.I2V_FIRST_TAIL,), "1080P", ("first_frame", "last_frame"), VideoModelSupport.HISTORICAL),
        )
        refreshed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        return VideoModelCatalogSnapshot.create(
            provider=self.provider,
            backend=VideoProviderBackend.API,
            region=VOLCENGINE_REGION,
            refreshed_at=refreshed_at,
            adapter_version="2.0",
            models=models,
            source="https://docs.volcengine.com/docs/jimeng-ai/product-overview?lang=zh",
        )

    def prepare(self, snapshot: VideoModelCatalogSnapshot, model: str, mode: VideoGenerationMode, parameters: dict[str, Any]) -> dict[str, Any]:
        profile = snapshot.model(model)
        if profile.support is VideoModelSupport.DISCOVERED_UNPROFILED:
            raise ValueError("model is discovered-unprofiled and cannot be submitted through the API")
        if profile.support is VideoModelSupport.HISTORICAL:
            raise ValueError("model is historical and cannot be submitted through the current API")
        if mode not in profile.supported_modes:
            raise ValueError("model does not support requested generation mode")
        build_jimeng_submit_body(model=model, mode=mode, parameters=parameters)
        return {"schema_version": 1, "provider": "jimeng", "backend": "api", "region": VOLCENGINE_REGION, "model": model, "mode": mode.value, "parameters": dict(parameters), "endpoint": profile.endpoint}

    @staticmethod
    def _response_data(response: dict[str, Any]) -> dict[str, Any]:
        if "code" not in response and isinstance(response.get("task_id"), str):
            return response
        raw_code = response.get("code", response.get("status", 0))
        try:
            code = int(raw_code)
        except (TypeError, ValueError) as error:
            raise RuntimeError("Jimeng response did not include a numeric status code") from error
        data = response.get("data")
        if code != 10000 or not isinstance(data, dict):
            message = str(response.get("message", "Jimeng request failed"))
            raise RuntimeError(f"Jimeng request failed with code {code}: {message}")
        return data

    def submit(self, prepared: dict[str, Any]) -> dict[str, Any]:
        parameters = dict(prepared.get("parameters", prepared))
        mode = VideoGenerationMode(prepared.get("mode", parameters.get("generation_mode", VideoGenerationMode.T2V.value)))
        model = str(prepared.get("model") or _model_for_mode(mode, parameters))
        body = build_jimeng_submit_body(model=model, mode=mode, parameters=parameters)
        path = _action_path(VOLCENGINE_SUBMIT_ACTION)
        response = self.transport.request("POST", path, body=body, headers=self._headers(path, body))
        data = self._response_data(response)
        task_id = data.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise RuntimeError("Jimeng did not return a task id")
        return {"schema_version": 1, "provider": "jimeng", "backend": "api", "external_task_id": task_id, "status": "submitted", "model": model}

    def _query_result(self, external_task_id: str, model: str | None = None) -> dict[str, Any]:
        if not isinstance(external_task_id, str) or not external_task_id.strip():
            raise ValueError("Jimeng task id must not be empty")
        req_key = model or JIMENG_PRO_MODEL
        body = {"req_key": req_key, "task_id": external_task_id}
        path = _action_path(VOLCENGINE_QUERY_ACTION)
        response = self.transport.request("POST", path, body=body, headers=self._headers(path, body))
        return self._response_data(response)

    def query(self, external_task_id: str, *, model: str | None = None) -> dict[str, Any]:
        data = self._query_result(external_task_id, model)
        provider_status = str(data.get("status", "unknown"))
        if provider_status == "done":
            status = "completed" if data.get("video_url") else "failed"
        elif provider_status in {"not_found", "expired"}:
            status = "failed"
        else:
            status = "running"
        return {"schema_version": 1, "provider": "jimeng", "backend": "api", "external_task_id": external_task_id, "status": status, "task_status": provider_status}

    def download(self, external_task_id: str, output_path: Path, *, model: str | None = None) -> dict[str, Any]:
        data = self._query_result(external_task_id, model)
        if str(data.get("status")) != "done":
            raise RuntimeError(f"Jimeng task is not done: {data.get('status', 'unknown')}")
        video_url = data.get("video_url")
        if not isinstance(video_url, str) or not video_url.strip():
            raise RuntimeError("Jimeng completed task did not return a video URL")
        downloaded_path = Path(self.transport.download(video_url, output_path))
        if not downloaded_path.is_file() or downloaded_path.stat().st_size == 0:
            raise RuntimeError("Jimeng video download is empty")
        return {"schema_version": 1, "provider": "jimeng", "backend": "api", "external_task_id": external_task_id, "status": "downloaded", "path": str(downloaded_path)}

    def preflight_cli(self, executable: Path, *, runner: Callable[[list[str]], tuple[int, str, str]] | None = None) -> dict[str, Any]:
        run = runner or self._run_cli
        code, stdout, _ = run([str(executable), "--version"])
        return {"schema_version": 1, "provider": "jimeng", "backend": "cli", "available": code == 0, "authenticated": code == 0, "version": stdout.strip() if code == 0 else None, "reason": None if code == 0 else "dreamina is unavailable"}

    def query_cli_attempt(self, attempt: dict[str, Any], executable: Path, *, runner: Callable[[list[str]], tuple[int, str, str]] | None = None) -> dict[str, Any]:
        if attempt.get("backend") != "cli":
            raise ValueError("backend-specific task cannot be queried through CLI")
        run = runner or self._run_cli
        code, stdout, _ = run([str(executable), "video", "query", str(attempt["external_task_id"])])
        if code != 0:
            raise RuntimeError("dreamina query failed")
        return {"schema_version": 1, "provider": "jimeng", "backend": "cli", "external_task_id": attempt["external_task_id"], "status": stdout.strip()}

    @staticmethod
    def _run_cli(argv: list[str]) -> tuple[int, str, str]:
        result = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", shell=False, check=False)
        return result.returncode, result.stdout, result.stderr


def run_command(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    adapter = JimengAdapter(transport=_UrllibTransport())
    if command == "capabilities":
        return {"schema_version": 1, "provider": "jimeng", "backend": payload.get("backend", "api"), "operations": ["capabilities", "models", "preflight", "estimate", "prepare", "submit", "query", "download"]}
    if command == "preflight":
        return adapter.preflight_api() if payload.get("backend", "api") == "api" else adapter.preflight_cli(Path(payload.get("executable", "dreamina")))
    if command == "models":
        return adapter.models().to_dict()
    if command == "estimate":
        return adapter.estimate(payload)
    if command == "prepare":
        snapshot = VideoModelCatalogSnapshot.from_dict(payload["snapshot"])
        return adapter.prepare(snapshot, str(payload["model"]), VideoGenerationMode(payload["mode"]), dict(payload.get("parameters", {})))
    if command == "submit":
        return adapter.submit(payload)
    if command == "query":
        return adapter.query(str(payload["external_task_id"]), model=payload.get("model"))
    if command == "download":
        return adapter.download(str(payload["external_task_id"]), Path(str(payload["output_path"])), model=payload.get("model"))
    raise ValueError(f"unsupported Jimeng command: {command}")


def main(
    argv: list[str] | None = None,
    input_stream: Any | None = None,
    output_stream: Any | None = None,
) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 1:
        raise SystemExit("usage: jimeng_video.py <command>")
    payload = read_utf8_json(input_stream)
    write_utf8_json(run_command(arguments[0], payload), output_stream)
    return 0


class _UrllibTransport:
    def __init__(self, base_url: str = VOLCENGINE_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")

    def request(self, method: str, path: str, *, body: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
        request = urllib.request.Request(self.base_url + path, method=method, headers=headers or {})
        if body is not None:
            request.data = _json_bytes(body)
        with urllib.request.urlopen(request, timeout=120) as response:
            value = json.loads(response.read().decode("utf-8"))
        if not isinstance(value, dict):
            raise RuntimeError("Jimeng returned a non-object response")
        return value

    def download(self, url: str, path: Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".part")
        with urllib.request.urlopen(url, timeout=120) as response:
            temporary.write_bytes(response.read())
        os.replace(temporary, destination)
        return destination
