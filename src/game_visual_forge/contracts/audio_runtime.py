from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Any


LOCAL_CONFIG_NAME = "game-visual-forge.local.json"


def _absolute_path(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be an absolute path")
    candidate = value.strip()
    if not Path(candidate).is_absolute() and not PureWindowsPath(candidate).is_absolute():
        raise ValueError(f"{field} must be an absolute path")
    return str(Path(candidate))


@dataclass(frozen=True)
class StableAudioRuntimeConfig:
    schema_version: int
    root: str
    python_executable: str

    @staticmethod
    def standard_python(root: Path, platform: str = sys.platform) -> Path:
        root = Path(root)
        if platform.startswith("win"):
            return root / "runtime" / ".venv" / "Scripts" / "python.exe"
        return root / "runtime" / ".venv" / "bin" / "python"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "StableAudioRuntimeConfig":
        if not isinstance(value, dict) or int(value.get("schema_version", 0)) != 1:
            raise ValueError("schema_version must be 1")
        stable = value.get("stable_audio")
        if not isinstance(stable, dict):
            raise ValueError("stable_audio must be an object")
        return cls(
            1,
            _absolute_path(stable.get("root"), "stable_audio.root"),
            _absolute_path(stable.get("python_executable"), "stable_audio.python_executable"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "stable_audio": {
                "root": self.root,
                "python_executable": self.python_executable,
            },
        }


@dataclass(frozen=True)
class StableAudioRuntimeResolution:
    source: str
    root: Path
    python_executable: Path
    config_path: Path | None = None

    @property
    def model_cache(self) -> Path:
        return self.root / "models" / "huggingface"

    @property
    def uv_cache(self) -> Path:
        return self.root / "cache" / "uv"

    @property
    def temp(self) -> Path:
        return self.root / "temp"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "source": self.source,
            "root": str(self.root),
            "python_executable": str(self.python_executable),
            "config_path": None if self.config_path is None else str(self.config_path),
            "model_cache": str(self.model_cache),
            "uv_cache": str(self.uv_cache),
            "temp": str(self.temp),
        }


def stable_audio_child_environment(
    root: Path,
    *,
    base: dict[str, str] | None = None,
    offline: bool,
) -> dict[str, str]:
    selected = Path(root).resolve()
    environment = dict(os.environ if base is None else base)
    model_cache = selected / "models" / "huggingface"
    environment.update(
        {
            "HF_HOME": str(model_cache),
            "HUGGINGFACE_HUB_CACHE": str(model_cache / "hub"),
            "TORCH_HOME": str(selected / "cache" / "torch"),
            "UV_CACHE_DIR": str(selected / "cache" / "uv"),
            "PIP_CACHE_DIR": str(selected / "cache" / "pip"),
            "TEMP": str(selected / "temp"),
            "TMP": str(selected / "temp"),
        }
    )
    if offline:
        environment.update(
            {
                "HF_HUB_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
                "HF_DATASETS_OFFLINE": "1",
            }
        )
    return environment
