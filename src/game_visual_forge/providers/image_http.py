from __future__ import annotations

import hashlib
import base64
import io
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from game_visual_forge.contracts.pathing import normalize_repo_relative_path
from game_visual_forge.contracts.provider import ExternalProvider, ProviderPreflight


MAX_IMAGE_BYTES = 128 * 1024 * 1024
_SECRET_FIELDS = {
    "api_key", "access_key", "secret_key", "secret", "token", "authorization",
    "cookie", "credential", "base64", "binary_data_base64",
}


class ImageApiError(RuntimeError):
    def __init__(self, code: str, *, definite_rejection: bool = False, external_task_id=None) -> None:
        self.code = safe_error_code(code)
        super().__init__(f"image provider request failed ({self.code})")
        self.external_task_id = valid_task_id(external_task_id)
        self.definite_rejection = definite_rejection and self.external_task_id is None


def safe_error_code(value):
    code = str(value)
    return code if re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", code) else "invalid_error_code"


def valid_task_id(value):
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,256}", value) else None


def response_task_id(response):
    if isinstance(response, dict):
        for key in ("data", "output"):
            value = response.get(key)
            if isinstance(value, dict) and valid_task_id(value.get("task_id")):
                return value["task_id"]
    return None


def json_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def preflight(provider: ExternalProvider, names: tuple[str, ...]) -> dict[str, Any]:
    configured = all(os.environ.get(name) for name in names)
    reason = "credentials configured; live authentication unverified" if configured else "configure " + ", ".join(names)
    try:
        from PIL import Image  # noqa: F401
        image_runtime = True
    except (ImportError, OSError):
        image_runtime = False
        reason += "; Pillow image runtime is required"
    value = ProviderPreflight(1, provider, configured and image_runtime, configured, None, "1.0", None, reason).to_dict()
    value["authentication_verified"] = False
    value["image_runtime_available"] = image_runtime
    return value


def check_parameters(parameters: dict[str, Any], allowed: set[str], prompt_limit: int, reference_limit: int) -> dict[str, Any]:
    assert_safe(parameters)
    unsupported = set(parameters) - allowed - {"prompt", "references"}
    if unsupported:
        raise ValueError("unsupported image parameters: " + ", ".join(sorted(unsupported)))
    value = dict(parameters)
    prompt = value.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt.strip()) > prompt_limit:
        raise ValueError(f"image prompt must contain 1–{prompt_limit} characters")
    value["prompt"] = prompt.strip()
    references = value.setdefault("references", [])
    if not isinstance(references, list) or len(references) > reference_limit:
        raise ValueError(f"at most {reference_limit} reference images are supported")
    return value


def image_data_uri(data: bytes) -> str:
    from PIL import Image
    with Image.open(io.BytesIO(data)) as image:
        mime = Image.MIME.get(image.format, "image/png")
    return f"data:{mime};base64," + base64.b64encode(data).decode("ascii")


def integer(value: Any, minimum: int, maximum: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer from {minimum} to {maximum}")
    return value


def boolean_parameters(parameters: dict[str, Any], names: tuple[str, ...]) -> None:
    for name in names:
        if name in parameters and not isinstance(parameters[name], bool):
            raise ValueError(f"{name} must be boolean")


def assert_safe(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower().replace("-", "_") in _SECRET_FIELDS:
                raise ValueError("credentials and inline media cannot be persisted")
            assert_safe(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            assert_safe(child)
    elif isinstance(value, str):
        if ";base64," in value.lower() or "bearer " in value.lower():
            raise ValueError("credentials and inline media cannot be persisted")
        if value.startswith(("http://", "https://")):
            public_url(value)


def public_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("image references require an HTTP(S) URL without embedded credentials")
    sensitive_queries = {"signature", "sig", "token", "access_token", "x-amz-signature", "x-oss-signature", "ossaccesskeyid"}
    if any(key.lower() in sensitive_queries for key, _ in urllib.parse.parse_qsl(parsed.query)):
        raise ValueError("transient signed URLs cannot be persisted as image references")
    return value


def repo_path(root: Path, value: str) -> Path:
    relative = normalize_repo_relative_path(value, field_name="image path")
    destination = (root.resolve() / relative).resolve()
    if not destination.is_relative_to(root.resolve()):
        raise ValueError("image path must stay inside the repository")
    return destination


@contextmanager
def file_lock(path: Path):
    """Use an OS lock so competing processes cannot submit the same attempt."""
    lock_path = path.with_name(path.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if sys.platform == "win32":
            import msvcrt
            lock = lambda: msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            unlock = lambda: msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            lock = lambda: fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            unlock = lambda: fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        try:
            lock()
        except OSError as error:
            raise ValueError("image attempt is busy in another process") from error
        try:
            yield
        finally:
            unlock()


class ImageHttpTransport:
    def request(self, method: str, url: str, *, body=None, headers=None, timeout: int = 120) -> dict[str, Any]:
        data = None if body is None else json_bytes(body)
        request = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read(128 * 1024 * 1024 + 1)
        except urllib.error.HTTPError as error:
            # Even a contradictory error response may contain a recoverable ID.
            try:
                error_payload = json.loads(error.read(1024 * 1024).decode("utf-8"))
            except (OSError, UnicodeDecodeError, ValueError):
                error_payload = None
            task_id = response_task_id(error_payload)
            raise ImageApiError(f"http_{error.code}", definite_rejection=400 <= error.code < 500, external_task_id=task_id) from None
        if len(raw) > 128 * 1024 * 1024:
            raise ImageApiError("response_too_large")
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as error:
            raise ImageApiError("invalid_json") from error
        if not isinstance(value, dict):
            raise ImageApiError("invalid_response")
        return value

    def read_image(self, url: str) -> bytes:
        # Result URLs are ephemeral and used only in memory. They may be signed.
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("provider image URL must use HTTP(S)")
        try:
            with urllib.request.urlopen(url, timeout=120) as response:
                data = response.read(MAX_IMAGE_BYTES + 1)
        except urllib.error.HTTPError as error:
            raise ImageApiError(f"download_http_{error.code}") from None
        if not data or len(data) > MAX_IMAGE_BYTES:
            raise ValueError("image download is empty or exceeds 128 MiB")
        return data

    def download(self, url: str, path: Path) -> Path:
        path.write_bytes(self.read_image(url))
        return path


def inspect_reference(data: bytes, *, provider: str) -> None:
    from PIL import Image

    limit = {"minimax": 64, "jimeng": 15, "dreamina": 15, "wanxiang": 20}[provider] * 1024 * 1024
    if not data or len(data) > limit:
        raise ValueError("reference image exceeds the provider file-size limit")
    with Image.open(io.BytesIO(data)) as image:
        image.verify()
    with Image.open(io.BytesIO(data)) as image:
        width, height = image.size
        if provider == "minimax":
            if image.format not in {"JPEG", "PNG", "WEBP"} or not (128 <= min(width, height) and max(width, height) <= 8192) or max(width, height) / min(width, height) > 4:
                raise ValueError("MiniMax references must be JPEG/PNG/WEBP, 128–8192px, and within 4:1")
        elif provider in {"jimeng", "dreamina"}:
            if image.format not in {"JPEG", "PNG"} or max(width, height) > 4096 or not 1 / 3 <= width / height <= 3:
                raise ValueError("Jimeng references must be JPEG/PNG up to 4096px and within 1:3–3:1")
        else:
            if image.format not in {"JPEG", "PNG", "BMP", "WEBP"} or not (240 <= min(width, height) and max(width, height) <= 8000) or not 1 / 8 <= width / height <= 8:
                raise ValueError("Wan references must be 240–8000px and within 1:8–8:1")
            if "A" in image.getbands() or "transparency" in image.info:
                raise ValueError("Wan reference images must have no alpha channel")


def reference_bytes(reference: dict[str, Any], root: Path, transport) -> bytes:
    if reference.get("path"):
        path = repo_path(root, str(reference["path"]))
        if path.stat().st_size > 64 * 1024 * 1024:
            raise ValueError("reference image exceeds 64 MB")
        return path.read_bytes()
    return transport.read_image(public_url(str(reference["url"])))


def bind_references(references: list[dict[str, Any]], root: Path, provider: str, transport) -> list[dict[str, Any]]:
    bound = []
    for reference in references:
        if not isinstance(reference, dict) or set(reference) - {"path", "url", "sha256"}:
            raise ValueError("each reference must contain path or url and optional sha256")
        if bool(reference.get("path")) == bool(reference.get("url")):
            raise ValueError("reference requires exactly one of path or url")
        if provider in {"jimeng", "dreamina"} and reference.get("path"):
            raise ValueError("Jimeng references require public image URLs")
        data = reference_bytes(reference, root, transport)
        inspect_reference(data, provider=provider)
        digest = hashlib.sha256(data).hexdigest()
        if reference.get("sha256") and reference["sha256"] != digest:
            raise ValueError("reference SHA-256 does not match")
        bound.append({**reference, "sha256": digest})
    return bound


def verify_references(references, root: Path, provider: str, transport) -> list[bytes]:
    data_items = []
    for reference in references:
        data = reference_bytes(reference, root, transport)
        if hashlib.sha256(data).hexdigest() != reference["sha256"]:
            raise ValueError("reference changed after preparation")
        inspect_reference(data, provider=provider)
        data_items.append(data)
    return data_items
