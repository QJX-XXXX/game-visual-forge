from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

from game_visual_forge.contracts.provider import ExternalProvider
from game_visual_forge.contracts.video_provider import VideoProviderBackend


class JsonTransport(Protocol):
    def request(self, method: str, path: str, *, body: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]: ...


@dataclass(frozen=True)
class SignedRequest:
    authorization: str
    headers: dict[str, str]


def sign_volcengine_request(*, method: str, url: str, headers: dict[str, str], body: dict[str, Any], access_key: str, secret_key: str, now: str) -> SignedRequest:
    canonical_body = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    body_hash = hashlib.sha256(canonical_body.encode("utf-8")).hexdigest()
    canonical = "\n".join((method.upper(), url, body_hash, now))
    signature = hmac.new(secret_key.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
    result_headers = dict(headers)
    result_headers["X-Date"] = now
    result_headers["Authorization"] = f"HMAC-SHA256 AccessKey={access_key}, Signature={signature}"
    return SignedRequest(result_headers["Authorization"], result_headers)


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

    def _headers(self, body: dict[str, Any]) -> dict[str, str]:
        access_key, secret_key = self._credentials()
        return sign_volcengine_request(method="POST", url="/api/v1/video/generate", headers={"Content-Type": "application/json"}, body=body, access_key=access_key, secret_key=secret_key, now="2026-08-09T00:00:00Z").headers

    def preflight_api(self) -> dict[str, Any]:
        try:
            self._credentials()
        except RuntimeError as error:
            return {"schema_version": 1, "provider": "jimeng", "backend": "api", "available": False, "authenticated": False, "reason": str(error)}
        return {"schema_version": 1, "provider": "jimeng", "backend": "api", "available": True, "authenticated": True}

    def estimate(self, parameters: dict[str, Any]) -> dict[str, Any]:
        return {"schema_version": 1, "provider": "jimeng", "currency": None, "amount": None, "verified": False, "notice": "Jimeng estimate must be verified in the provider console before paid confirmation"}

    def submit(self, parameters: dict[str, Any]) -> dict[str, Any]:
        payload = {key: value for key, value in parameters.items() if key not in {"access_key", "secret_key", "authorization"}}
        response = self.transport.request("POST", "/api/v1/video/generate", body=payload, headers=self._headers(payload))
        task_id = response.get("task_id", response.get("id"))
        if not task_id:
            raise RuntimeError("Jimeng did not return a task id")
        return {"schema_version": 1, "provider": "jimeng", "backend": "api", "external_task_id": str(task_id), "status": str(response.get("status", "submitted"))}

    def query(self, external_task_id: str) -> dict[str, Any]:
        access_key, secret_key = self._credentials()
        signed = sign_volcengine_request(method="GET", url=f"/api/v1/video/tasks/{external_task_id}", headers={}, body={}, access_key=access_key, secret_key=secret_key, now="2026-08-09T00:00:00Z")
        response = self.transport.request("GET", f"/api/v1/video/tasks/{external_task_id}", headers=signed.headers)
        return {"schema_version": 1, "provider": "jimeng", "backend": "api", "external_task_id": external_task_id, "status": str(response.get("status", "unknown"))}

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
    if command == "estimate":
        return adapter.estimate(payload)
    if command == "submit":
        return adapter.submit(payload)
    if command == "query":
        return adapter.query(str(payload["external_task_id"]))
    raise ValueError(f"unsupported Jimeng command: {command}")


class _UrllibTransport:
    def request(self, method: str, path: str, *, body: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
        raise RuntimeError("live Jimeng transport is available only through configured adapter integration")
