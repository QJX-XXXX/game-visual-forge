from __future__ import annotations

import re
from pathlib import PurePosixPath


_WINDOWS_DRIVE_PATTERN = re.compile(r"^[A-Za-z]:")


def normalize_repo_relative_path(value: str, *, field_name: str) -> str:
    normalized = value.replace("\\", "/").strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    if normalized.startswith("/") or _WINDOWS_DRIVE_PATTERN.match(normalized):
        raise ValueError(f"{field_name} must be repository-relative")

    candidate = PurePosixPath(normalized)
    for segment in candidate.parts:
        if segment in {".", ".."}:
            raise ValueError(
                f"{field_name} must not contain '.' or '..' path segments"
            )

    return candidate.as_posix()
