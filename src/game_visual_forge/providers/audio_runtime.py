from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from game_visual_forge.contracts.audio_runtime import (
    LOCAL_CONFIG_NAME,
    StableAudioRuntimeConfig,
    StableAudioRuntimeResolution,
    stable_audio_child_environment,
)
from game_visual_forge.errors import ErrorCode, ForgeError


def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _python_can_import(python_executable: Path, module: str) -> bool:
    try:
        completed = subprocess.run(
            [str(python_executable), "-c", f"import {module}"],
            capture_output=True,
            text=False,
            timeout=15,
            shell=False,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


def _runtime_error(message: str, *, action: str = "install-stable-audio-3") -> ForgeError:
    return ForgeError(
        ErrorCode.PROVIDER_UNAVAILABLE,
        message,
        recoverable=True,
        context={"status": "needs_user_action", "action": action},
    )


def _infer_root(python_executable: Path) -> Path:
    resolved = python_executable.resolve()
    for parent in resolved.parents:
        if parent.name.lower() == "runtime":
            return parent.parent
    return resolved.parent


def _resolution_from_python(
    python_executable: Path,
    source: str,
    *,
    root: Path | None = None,
    config_path: Path | None = None,
) -> StableAudioRuntimeResolution:
    return StableAudioRuntimeResolution(
        source=source,
        root=(root or _infer_root(python_executable)).resolve(),
        python_executable=python_executable.resolve(),
        config_path=None if config_path is None else config_path.resolve(),
    )


def _load_config(path: Path) -> StableAudioRuntimeConfig:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _runtime_error(f"invalid Stable Audio local config: {path}", action="repair-stable-audio-config") from error
    return StableAudioRuntimeConfig.from_dict(value)


def _resolution_from_config(path: Path) -> StableAudioRuntimeResolution:
    config = _load_config(path)
    root = Path(config.root).resolve()
    python_executable = Path(config.python_executable).resolve()
    if not python_executable.is_file():
        raise _runtime_error(f"configured Stable Audio Python does not exist: {python_executable}", action="repair-stable-audio-config")
    if not _python_can_import(python_executable, "stable_audio_3"):
        raise _runtime_error("configured Stable Audio Python cannot import stable_audio_3", action="repair-stable-audio-runtime")
    return _resolution_from_python(python_executable, "local-config", root=root, config_path=path)


def _validate_explicit(python_executable: Path) -> StableAudioRuntimeResolution:
    selected = Path(python_executable).resolve()
    if not selected.is_file() or not _python_can_import(selected, "stable_audio_3"):
        raise _runtime_error(f"explicit Stable Audio Python cannot import stable_audio_3: {selected}", action="repair-stable-audio-runtime")
    return _resolution_from_python(selected, "explicit-python")


def resolve_stable_audio_runtime(
    repo_root: Path,
    *,
    explicit_python: Path | None = None,
    current_python: Path = Path(sys.executable),
) -> StableAudioRuntimeResolution:
    if explicit_python is not None:
        return _validate_explicit(explicit_python)
    config_path = Path(repo_root).resolve() / LOCAL_CONFIG_NAME
    if config_path.is_file():
        return _resolution_from_config(config_path)
    if _python_can_import(current_python, "stable_audio_3"):
        return _resolution_from_python(current_python, "current-python")
    command = shutil.which("stable-audio")
    if command:
        command_path = Path(command).resolve()
        sibling = command_path.parent / ("python.exe" if os.name == "nt" else "python")
        if _python_can_import(sibling, "stable_audio_3"):
            return _resolution_from_python(sibling, "path-command")
    raise _runtime_error("Stable Audio 3 runtime is not configured")


def show_stable_audio_runtime(repo_root: Path) -> StableAudioRuntimeResolution:
    return resolve_stable_audio_runtime(repo_root)


def configure_stable_audio_runtime(
    repo_root: Path,
    root: Path,
    python_executable: Path | None,
    *,
    replace: bool,
) -> StableAudioRuntimeResolution:
    repo = Path(repo_root).resolve()
    repo.mkdir(parents=True, exist_ok=True)
    selected_root = Path(root).resolve()
    selected_python = Path(python_executable).resolve() if python_executable is not None else StableAudioRuntimeConfig.standard_python(selected_root)
    if not selected_python.is_file():
        raise _runtime_error(f"Stable Audio Python does not exist: {selected_python}", action="repair-stable-audio-runtime")
    if not _python_can_import(selected_python, "stable_audio_3"):
        raise _runtime_error("Stable Audio Python cannot import stable_audio_3", action="repair-stable-audio-runtime")
    target = repo / LOCAL_CONFIG_NAME
    new_config = StableAudioRuntimeConfig(1, str(selected_root), str(selected_python))
    if target.is_file():
        existing = _load_config(target)
        if existing.to_dict() == new_config.to_dict():
            return _resolution_from_python(selected_python, "local-config", root=selected_root, config_path=target)
        if not replace:
            raise ValueError("existing Stable Audio config differs; pass --replace to overwrite")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=repo,
            prefix=f"{LOCAL_CONFIG_NAME}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(new_config.to_dict(), handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return _resolution_from_python(selected_python, "local-config", root=selected_root, config_path=target)


__all__ = [
    "LOCAL_CONFIG_NAME",
    "configure_stable_audio_runtime",
    "repository_root",
    "resolve_stable_audio_runtime",
    "show_stable_audio_runtime",
    "stable_audio_child_environment",
]
