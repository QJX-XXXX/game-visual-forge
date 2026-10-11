from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests._bootstrap import ROOT  # noqa: F401

from game_visual_forge.contracts.audio_runtime import LOCAL_CONFIG_NAME, StableAudioRuntimeConfig, stable_audio_child_environment
from game_visual_forge.providers.audio_runtime import configure_stable_audio_runtime, resolve_stable_audio_runtime


def write_fake_python(root: Path) -> Path:
    path = root / "runtime" / ".venv" / "Scripts" / "python.exe"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"fake")
    return path


class AudioRuntimeConfigTests(unittest.TestCase):
    def test_config_round_trips_absolute_paths(self) -> None:
        config = StableAudioRuntimeConfig.from_dict(
            {
                "schema_version": 1,
                "stable_audio": {
                    "root": r"G:\AI\stable-audio-3",
                    "python_executable": r"G:\AI\stable-audio-3\runtime\.venv\Scripts\python.exe",
                },
            }
        )
        self.assertEqual(config.to_dict()["stable_audio"]["root"], r"G:\AI\stable-audio-3")

    def test_config_rejects_relative_root_and_unknown_schema(self) -> None:
        with self.assertRaisesRegex(ValueError, "absolute"):
            StableAudioRuntimeConfig.from_dict(
                {
                    "schema_version": 1,
                    "stable_audio": {"root": "relative", "python_executable": "relative/python"},
                }
            )
        with self.assertRaisesRegex(ValueError, "schema_version"):
            StableAudioRuntimeConfig.from_dict({"schema_version": 2, "stable_audio": {}})

    def test_standard_python_layouts(self) -> None:
        root = Path(r"G:\Audio Runtime")
        self.assertEqual(StableAudioRuntimeConfig.standard_python(root, "win32"), root / "runtime" / ".venv" / "Scripts" / "python.exe")
        self.assertEqual(StableAudioRuntimeConfig.standard_python(root, "linux"), root / "runtime" / ".venv" / "bin" / "python")

    def test_configure_is_atomic_idempotent_and_requires_replace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            repo.mkdir()
            runtime = Path(directory) / "runtime-a"
            python = write_fake_python(runtime)
            with patch("game_visual_forge.providers.audio_runtime._python_can_import", return_value=True):
                first = configure_stable_audio_runtime(repo, runtime, python, replace=False)
                second = configure_stable_audio_runtime(repo, runtime, python, replace=False)
            self.assertEqual(first.to_dict(), second.to_dict())
            config = repo / LOCAL_CONFIG_NAME
            original = config.read_bytes()
            self.assertEqual(list(repo.glob(f"{LOCAL_CONFIG_NAME}.*.tmp")), [])
            other_root = Path(directory) / "runtime-b"
            other = write_fake_python(other_root)
            with patch("game_visual_forge.providers.audio_runtime._python_can_import", return_value=True):
                with self.assertRaisesRegex(ValueError, "--replace"):
                    configure_stable_audio_runtime(repo, other_root, other, replace=False)
            self.assertEqual(config.read_bytes(), original)

    def test_resolver_prefers_explicit_then_local_config_then_current_python(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            repo.mkdir()
            explicit = Path(directory) / "explicit" / "python.exe"
            explicit.parent.mkdir()
            explicit.write_bytes(b"fake")
            with patch("game_visual_forge.providers.audio_runtime._python_can_import", return_value=True):
                selected = resolve_stable_audio_runtime(repo, explicit_python=explicit)
            self.assertEqual(selected.source, "explicit-python")
            self.assertEqual(selected.python_executable, explicit.resolve())

            configured_root = Path(directory) / "音频 环境"
            configured_python = configured_root / "runtime" / ".venv" / "Scripts" / "python.exe"
            configured_python.parent.mkdir(parents=True)
            configured_python.write_bytes(b"fake")
            (repo / LOCAL_CONFIG_NAME).write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "stable_audio": {
                            "root": str(configured_root.resolve()),
                            "python_executable": str(configured_python.resolve()),
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with patch("game_visual_forge.providers.audio_runtime._python_can_import", return_value=True):
                selected = resolve_stable_audio_runtime(repo, current_python=Path(sys.executable))
            self.assertEqual(selected.source, "local-config")
            self.assertEqual(selected.root, configured_root.resolve())

    def test_resolver_uses_current_python_then_path_sibling(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            repo.mkdir()
            current = Path(directory) / "current-python.exe"
            current.write_bytes(b"fake")
            with patch("game_visual_forge.providers.audio_runtime._python_can_import", side_effect=lambda path, module: path == current):
                selected = resolve_stable_audio_runtime(repo, current_python=current)
            self.assertEqual(selected.source, "current-python")

    def test_child_environment_keeps_every_cache_under_selected_root(self) -> None:
        previous_home = os.environ.get("HF_HOME")
        env = stable_audio_child_environment(Path(r"G:\Audio Runtime"), base={"PATH": "base"}, offline=True)
        self.assertEqual(env["HF_HOME"], r"G:\Audio Runtime\models\huggingface")
        self.assertEqual(env["TEMP"], r"G:\Audio Runtime\temp")
        self.assertEqual(env["HF_HUB_OFFLINE"], "1")
        self.assertEqual(os.environ.get("HF_HOME"), previous_home)


if __name__ == "__main__":
    unittest.main()
