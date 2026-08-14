from __future__ import annotations

import json
import unittest
from pathlib import Path

from tests._bootstrap import ROOT  # noqa: F401

from game_visual_forge.providers.stdio import run_utf8_json_process


WRAPPER = ROOT / "skills" / "forge-text-audio" / "scripts" / "providers" / "stable_audio.py"


class StableAudioProviderTests(unittest.TestCase):
    def test_models_command_reports_only_small_sfx(self) -> None:
        result = run_utf8_json_process(
            [__import__("sys").executable, str(WRAPPER), "models"],
            {"schema_version": 1},
            timeout_seconds=30,
        )
        self.assertEqual(result.returncode, 0)
        value = json.loads(result.stdout)
        self.assertEqual(value["models"], ["small-sfx"])
        self.assertEqual(value["model_repository"], "stabilityai/stable-audio-3-small-sfx")

    def test_preflight_never_requires_network_and_reports_missing_tools(self) -> None:
        result = run_utf8_json_process(
            [__import__("sys").executable, str(WRAPPER), "preflight"],
            {
                "schema_version": 1,
                "ffmpeg_executable": "definitely-missing-ffmpeg",
                "ffprobe_executable": "definitely-missing-ffprobe",
            },
            timeout_seconds=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value["model_id"], "small-sfx")
        self.assertFalse(value["ffmpeg_available"])
        self.assertFalse(value["ffprobe_available"])

    def test_wrapper_uses_offline_environment_and_official_python_api(self) -> None:
        source = WRAPPER.read_text(encoding="utf-8")
        for fragment in (
            'HF_HUB_OFFLINE',
            'TRANSFORMERS_OFFLINE',
            'local_files_only=True',
            'get_pretrained_model',
            'generate_diffusion_cond',
            'generate_diffusion_cond_inpaint',
        ):
            self.assertIn(fragment, source)
        self.assertNotIn('stable-audio --', source)


if __name__ == "__main__":
    unittest.main()
