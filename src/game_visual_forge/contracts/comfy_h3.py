from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .pathing import normalize_repo_relative_path


_DIGEST = re.compile(r"[0-9a-f]{64}")


def _digest(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise ValueError(f"{field} must be a SHA-256 hex digest")
    return value


def _optional_digest(value: Any, field: str) -> str | None:
    return None if value is None else _digest(value, field)


def _optional_text(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string or null")
    return value


@dataclass(frozen=True)
class ComfyH3WorkflowReport:
    """Sanitized, deterministic checks for a local MiniMax H3 graph."""

    schema_version: int
    workflow_sha256: str
    h3_node_count: int
    first_frame_connected: bool
    last_frame_connected: bool
    same_keyframe_source: bool
    seed_mode: str
    length: int | None
    local_only: bool
    errors: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        _digest(self.workflow_sha256, "workflow_sha256")
        if isinstance(self.h3_node_count, bool) or self.h3_node_count < 0:
            raise ValueError("h3_node_count must not be negative")
        if not isinstance(self.first_frame_connected, bool) or not isinstance(self.last_frame_connected, bool):
            raise TypeError("frame connection flags must be booleans")
        if not isinstance(self.same_keyframe_source, bool) or not isinstance(self.local_only, bool):
            raise TypeError("workflow flags must be booleans")
        if not isinstance(self.seed_mode, str) or not self.seed_mode.strip():
            raise ValueError("seed_mode must not be empty")
        if self.length is not None and (isinstance(self.length, bool) or self.length <= 0):
            raise ValueError("length must be positive or null")
        if not all(isinstance(error, str) and error.strip() for error in self.errors):
            raise ValueError("workflow errors must be non-empty strings")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "workflow_sha256": self.workflow_sha256,
            "h3_node_count": self.h3_node_count,
            "first_frame_connected": self.first_frame_connected,
            "last_frame_connected": self.last_frame_connected,
            "same_keyframe_source": self.same_keyframe_source,
            "seed_mode": self.seed_mode,
            "length": self.length,
            "local_only": self.local_only,
            "ok": self.ok,
            "errors": list(self.errors),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ComfyH3WorkflowReport":
        return cls(
            schema_version=int(value["schema_version"]),
            workflow_sha256=str(value["workflow_sha256"]),
            h3_node_count=int(value["h3_node_count"]),
            first_frame_connected=bool(value["first_frame_connected"]),
            last_frame_connected=bool(value["last_frame_connected"]),
            same_keyframe_source=bool(value["same_keyframe_source"]),
            seed_mode=str(value["seed_mode"]),
            length=None if value.get("length") is None else int(value["length"]),
            local_only=bool(value["local_only"]),
            errors=tuple(str(item) for item in value.get("errors", [])),
        )


@dataclass(frozen=True)
class ComfyH3GenerationRecord:
    """Recovery metadata that deliberately excludes secrets and raw responses."""

    schema_version: int
    request_fingerprint: str
    workflow_sha256: str
    prompt_sha256: str
    reference_paths: tuple[str, ...]
    reference_sha256: tuple[str, ...]
    model: str
    seed: int
    steps: int
    prompt_id: str | None = None
    terminal_status: str | None = None
    output_path: str | None = None
    output_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        _digest(self.request_fingerprint, "request_fingerprint")
        _digest(self.workflow_sha256, "workflow_sha256")
        _digest(self.prompt_sha256, "prompt_sha256")
        if len(self.reference_paths) != len(self.reference_sha256):
            raise ValueError("reference_paths and reference_sha256 must have the same length")
        object.__setattr__(self, "reference_paths", tuple(normalize_repo_relative_path(path, field_name="reference_paths") for path in self.reference_paths))
        for index, digest in enumerate(self.reference_sha256):
            _digest(digest, f"reference_sha256[{index}]")
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("model must not be empty")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError("seed must be an integer")
        if isinstance(self.steps, bool) or not isinstance(self.steps, int) or self.steps <= 0:
            raise ValueError("steps must be a positive integer")
        object.__setattr__(self, "prompt_id", _optional_text(self.prompt_id, "prompt_id"))
        object.__setattr__(self, "terminal_status", _optional_text(self.terminal_status, "terminal_status"))
        if self.output_path is not None:
            object.__setattr__(self, "output_path", normalize_repo_relative_path(self.output_path, field_name="output_path"))
        object.__setattr__(self, "output_sha256", _optional_digest(self.output_sha256, "output_sha256"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "request_fingerprint": self.request_fingerprint,
            "workflow_sha256": self.workflow_sha256,
            "prompt_sha256": self.prompt_sha256,
            "reference_paths": list(self.reference_paths),
            "reference_sha256": list(self.reference_sha256),
            "model": self.model,
            "seed": self.seed,
            "steps": self.steps,
            "prompt_id": self.prompt_id,
            "terminal_status": self.terminal_status,
            "output_path": self.output_path,
            "output_sha256": self.output_sha256,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ComfyH3GenerationRecord":
        return cls(
            schema_version=int(value["schema_version"]),
            request_fingerprint=str(value["request_fingerprint"]),
            workflow_sha256=str(value["workflow_sha256"]),
            prompt_sha256=str(value["prompt_sha256"]),
            reference_paths=tuple(str(item) for item in value.get("reference_paths", [])),
            reference_sha256=tuple(str(item) for item in value.get("reference_sha256", [])),
            model=str(value["model"]),
            seed=int(value["seed"]),
            steps=int(value["steps"]),
            prompt_id=value.get("prompt_id"),
            terminal_status=value.get("terminal_status"),
            output_path=value.get("output_path"),
            output_sha256=value.get("output_sha256"),
        )
