from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
from typing import Any

from game_visual_forge.contracts import ExternalProvider, RawImageRecord, SourceType
from game_visual_forge.errors import ErrorCode, ForgeError


def _load_pillow() -> Any:
    try:
        from PIL import Image
    except ImportError as error:
        raise ForgeError(
            ErrorCode.DEPENDENCY_MISSING,
            "Pillow is required for local image processing; install the image extra explicitly.",
            recoverable=True,
            context={"dependency": "Pillow", "extra": "image"},
        ) from error
    return Image


def resolve_repo_path(repo_root: Path, relative_or_local: Path) -> tuple[Path, str]:
    root = repo_root.resolve()
    path = relative_or_local.resolve()
    try:
        relative = path.relative_to(root)
    except ValueError as error:
        raise ForgeError(
            ErrorCode.INVALID_REQUEST,
            "image path must remain inside the repository root",
            recoverable=True,
            context={"field": "image_path"},
        ) from error
    return path, PurePosixPath(relative.as_posix()).as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ingest_image(
    repo_root: Path,
    image_path: Path,
    source_type: SourceType,
    request_fingerprint: str,
    *,
    provider: ExternalProvider | None = None,
    model: str | None = None,
    max_pixels: int = 67_108_864,
) -> RawImageRecord:
    try:
        Image = _load_pillow()
    except ImportError as error:
        raise ForgeError(
            ErrorCode.DEPENDENCY_MISSING,
            "Pillow is required for local image processing; install the image extra explicitly.",
            recoverable=True,
            context={"dependency": "Pillow", "extra": "image"},
        ) from error
    path, relative = resolve_repo_path(repo_root, image_path)
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            width, height = image.size
            media_format = image.format
    except (OSError, ValueError) as error:
        raise ForgeError(
            ErrorCode.IMAGE_UNREADABLE,
            "image cannot be decoded",
            recoverable=True,
            context={"path": relative},
        ) from error
    if width <= 0 or height <= 0 or width * height > max_pixels:
        raise ForgeError(
            ErrorCode.IMAGE_UNREADABLE,
            "image dimensions exceed configured limits",
            recoverable=True,
            context={"path": relative, "width": width, "height": height},
        )
    return RawImageRecord(
        schema_version=1,
        path=relative,
        sha256=sha256_file(path),
        width=width,
        height=height,
        media_format=media_format or "UNKNOWN",
        source_type=source_type,
        request_fingerprint=request_fingerprint,
        provider=provider,
        model=model,
    )


def verify_image_unchanged(repo_root: Path, record: RawImageRecord) -> None:
    path = repo_root.resolve() / PurePosixPath(record.path)
    try:
        current = sha256_file(path)
    except OSError as error:
        raise ForgeError(
            ErrorCode.IMAGE_CHANGED,
            "source image is no longer available",
            recoverable=True,
            context={"path": record.path},
        ) from error
    if current != record.sha256:
        raise ForgeError(
            ErrorCode.IMAGE_CHANGED,
            "source image changed after inspection",
            recoverable=True,
            context={"path": record.path},
        )
