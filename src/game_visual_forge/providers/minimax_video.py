from __future__ import annotations

import os
import subprocess
import json
import urllib.request
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

from game_visual_forge.contracts.provider import ExternalProvider
from game_visual_forge.contracts.video import VideoGenerationMode
from game_visual_forge.contracts.video_provider import VideoModelCatalogSnapshot, VideoModelProfile, VideoModelSupport, VideoProviderBackend


class JsonTransport(Protocol):
    def request(self, method: str, path: str, *, body: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]: ...


@dataclass(frozen=True)
class MiniMaxSubmitRequest:
    endpoint: str
    body: dict[str, Any]


def build_minimax_submit_request(*, model: str, mode: VideoGenerationMode, prompt: str, first_frame_url: str | None = None, last_frame_url: str | None = None, duration: int = 6) -> MiniMaxSubmitRequest:
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    if first_frame_url is not None:
        content.append({"type": "image_url", "image_url": {"url": first_frame_url, "role": "first_frame"}})
    if last_frame_url is not None:
        content.append({"type": "image_url", "image_url": {"url": last_frame_url, "role": "last_frame"}})
    return MiniMaxSubmitRequest("/v2/video_generation" if model == "MiniMax-H3" else "/v1/video_generation", {"model": model, "prompt": prompt, "duration": duration, "content": content, "mode": mode.value})


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
        profiles: list[VideoModelProfile | dict[str, Any]] = []
        for model_id in model_ids:
            if model_id == "MiniMax-H3":
                profiles.append(VideoModelProfile(1, self.provider, "MiniMax-H3", "v2", "/v2/video_generation", (VideoGenerationMode.T2V, VideoGenerationMode.I2V_FIRST, VideoGenerationMode.I2V_FIRST_TAIL, VideoGenerationMode.REFERENCE_TO_VIDEO), ("first_frame", "last_frame", "reference"), (6,), ("768P",), ("16:9", "9:16"), False, (VideoProviderBackend.API, VideoProviderBackend.CLI), "2026-08-09"))
            elif model_id:
                profiles.append({"model": str(model_id)})
        refreshed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        return VideoModelCatalogSnapshot.create(provider=self.provider, backend=VideoProviderBackend.API, region=self.region, refreshed_at=refreshed_at, adapter_version="1.0", models=tuple(profiles), source="minimax:/v1/models")

    def prepare(self, snapshot: VideoModelCatalogSnapshot, model: str, mode: VideoGenerationMode, parameters: dict[str, Any]) -> dict[str, Any]:
        profile = snapshot.model(model)
        if profile.support is VideoModelSupport.DISCOVERED_UNPROFILED:
            raise ValueError("model is discovered-unprofiled and cannot be submitted through the API")
        if mode not in profile.supported_modes:
            raise ValueError("model does not support requested generation mode")
        return {"schema_version": 1, "provider": "minimax", "backend": "api", "region": self.region, "model": model, "mode": mode.value, "parameters": dict(parameters), "endpoint": profile.endpoint}

    def estimate(self, prepared: dict[str, Any]) -> dict[str, Any]:
        return {"schema_version": 1, "provider": "minimax", "currency": None, "amount": None, "verified": False, "notice": "MiniMax estimate must be verified in the provider console before paid confirmation"}

    def submit(self, prepared: dict[str, Any]) -> dict[str, Any]:
        model = str(prepared["model"])
        mode = VideoGenerationMode(prepared.get("mode", VideoGenerationMode.T2V.value))
        parameters = dict(prepared.get("parameters", prepared))
        request = build_minimax_submit_request(model=model, mode=mode, prompt=str(parameters.get("prompt", "")), first_frame_url=parameters.get("first_frame_url"), last_frame_url=parameters.get("last_frame_url"), duration=int(parameters.get("duration", 6)))
        payload = self.transport.request("POST", request.endpoint, body=request.body, headers=self._headers())
        task_id = payload.get("task_id", payload.get("id"))
        if not task_id:
            raise RuntimeError("MiniMax did not return a task id")
        return {"schema_version": 1, "provider": "minimax", "backend": "api", "external_task_id": str(task_id), "status": str(payload.get("status", "submitted"))}

    def query(self, external_task_id: str) -> dict[str, Any]:
        payload = self.transport.request("GET", f"/v1/video_generation/{external_task_id}", headers=self._headers())
        return {"schema_version": 1, "provider": "minimax", "backend": "api", "external_task_id": external_task_id, "status": str(payload.get("status", "unknown"))}

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
    transport = _UrllibTransport(payload.get("base_url", ""))
    adapter = MiniMaxAdapter(region=str(payload.get("region", "global")), transport=transport)
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
