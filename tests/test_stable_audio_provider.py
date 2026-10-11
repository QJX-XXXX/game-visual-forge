from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests._bootstrap import ROOT  # noqa: F401

from game_visual_forge.providers.stdio import run_utf8_json_process


WRAPPER = ROOT / "skills" / "forge-text-audio" / "scripts" / "providers" / "stable_audio.py"


def load_provider():
    spec = importlib.util.spec_from_file_location("stable_audio_provider_under_test", WRAPPER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeTensor:
    ndim = 3

    def __init__(self, peak=2.0, overrange=80, count=100):
        self.peak = peak
        self.overrange = overrange
        self.count = count
        self.gain = 1.0
        self.converted_to = None

    def __getitem__(self, index):
        return self

    def cpu(self):
        return self

    def to(self, dtype):
        self.converted_to = dtype
        return self

    def abs(self):
        return self

    def max(self):
        return SimpleNamespace(item=lambda: self.peak)

    def __gt__(self, _value):
        return SimpleNamespace(sum=lambda: SimpleNamespace(item=lambda: self.overrange))

    def numel(self):
        return self.count

    def __mul__(self, gain):
        self.gain *= gain
        return self


class FakeTorch:
    float32 = object()

    class cuda:
        @staticmethod
        def is_available():
            return False


class FakeTorchaudio:
    loaded = []
    saved = []

    @classmethod
    def load(cls, path):
        cls.loaded.append(path)
        return FakeTensor(), 48000

    @classmethod
    def save(cls, path, audio, sample_rate, **kwargs):
        cls.saved.append((path, audio, sample_rate, kwargs))
        Path(path).write_bytes(b"fake wav")


class FakePretransform:
    decoded = []
    parameter_dtype = object()

    def parameters(self):
        yield SimpleNamespace(dtype=self.parameter_dtype)

    def decode(self, latents):
        self.decoded.append(latents)
        return FakeTensor()


class FakeModel:
    calls = []
    load_calls = []
    model_config = {"sample_size": 1234}
    model = SimpleNamespace(sample_rate=44100, pretransform=FakePretransform())

    @classmethod
    def from_pretrained(cls, name, **kwargs):
        if name != "small-sfx":
            raise AssertionError(name)
        cls.load_calls.append(kwargs)
        return cls()

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        print("official progress on stdout")
        return FakeTensor()


def base_payload(mode: str, output_path: Path) -> dict:
    payload = {
        "schema_version": 1,
        "mode": mode,
        "prompt": "dry wooden UI click",
        "duration_seconds": 1.5,
        "seed": 17,
        "output_path": str(output_path),
    }
    if mode != "text-to-audio":
        payload["source_path"] = "source.wav"
    if mode == "redraw":
        payload["redraw_strength"] = 0.4
    if mode == "inpaint":
        payload.update(edit_start_seconds=0.2, edit_end_seconds=0.8)
    if mode == "continue":
        payload.update(source_duration_seconds=1.0, join_guard_ms=20)
    return payload


class StableAudioProviderTests(unittest.TestCase):
    def test_models_command_reports_only_small_sfx(self) -> None:
        result = run_utf8_json_process(
            [sys.executable, str(WRAPPER), "models"],
            {"schema_version": 1},
            timeout_seconds=30,
        )
        self.assertEqual(result.returncode, 0)
        value = json.loads(result.stdout)
        self.assertEqual(value["models"], ["small-sfx"])
        self.assertEqual(value["model_repository"], "stabilityai/stable-audio-3-small-sfx")

    def test_preflight_never_requires_network_and_reports_missing_tools(self) -> None:
        result = run_utf8_json_process(
            [sys.executable, str(WRAPPER), "preflight"],
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

    def test_official_api_maps_all_four_modes(self) -> None:
        module = load_provider()
        FakeModel.calls = []
        FakeModel.load_calls = []
        FakeTorchaudio.loaded = []
        FakeTorchaudio.saved = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for mode in ("text-to-audio", "redraw", "inpaint", "continue"):
                with self.subTest(mode=mode), patch.object(module, "_load_backend", return_value=(FakeModel, FakeTorch, FakeTorchaudio)):
                    result = module._generate(base_payload(mode, root / f"{mode}.wav"))
                self.assertEqual(result["sample_rate"], 44100)
            text, redraw, inpaint, continuation = FakeModel.calls
            self.assertEqual(FakeModel.load_calls[0]["model_half"], True)
            self.assertTrue(all(call["model_half"] is False for call in FakeModel.load_calls[1:]))
            self.assertTrue(all(call["return_latents"] for call in FakeModel.calls))
            self.assertEqual(text["steps"], 8)
            self.assertEqual(text["cfg_scale"], 1.0)
            self.assertEqual(text["sample_size"], 1234)
            self.assertEqual(redraw["init_noise_level"], 0.4)
            self.assertTrue(all(call["sampler_type"] == "rk4" for call in (redraw, inpaint, continuation)))
            self.assertNotIn("sampler_type", text)
            self.assertEqual(inpaint["inpaint_mask_start_seconds"], 0.2)
            self.assertEqual(inpaint["inpaint_mask_end_seconds"], 0.8)
            self.assertEqual(continuation["inpaint_mask_start_seconds"], 0.98)
            self.assertEqual(continuation["inpaint_mask_end_seconds"], 1.5)
            self.assertTrue(all(call["inpaint_audio"][0] == 48000 for call in (inpaint, continuation)))
            self.assertTrue(all(item[2] == 44100 for item in FakeTorchaudio.saved))

    def test_generation_decodes_without_clamping_and_applies_no_boost_peak_protection(self) -> None:
        module = load_provider()
        FakeModel.calls = []
        FakeModel.model.pretransform.decoded = []
        FakeTorchaudio.saved = []
        with tempfile.TemporaryDirectory() as directory, patch.object(module, "_load_backend", return_value=(FakeModel, FakeTorch, FakeTorchaudio)):
            result = module._generate(base_payload("text-to-audio", Path(directory) / "output.wav"))

        self.assertTrue(FakeModel.calls[0]["return_latents"])
        self.assertEqual(len(FakeModel.model.pretransform.decoded), 1)
        self.assertIs(FakeModel.model.pretransform.decoded[0].converted_to, FakeModel.model.pretransform.parameter_dtype)
        self.assertAlmostEqual(result["audio_metrics"]["decoded_peak"], 2.0)
        self.assertEqual(result["audio_metrics"]["overrange_sample_count"], 80)
        self.assertLess(result["audio_metrics"]["peak_protection_gain"], 1.0)
        self.assertLess(FakeTorchaudio.saved[0][1].gain, 1.0)

    def test_main_keeps_stdout_as_one_json_object(self) -> None:
        module = load_provider()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output.wav"
            payload = base_payload("text-to-audio", output)
            stdin = io.BytesIO(json.dumps(payload).encode("utf-8"))
            stdout = io.BytesIO()
            stderr = io.StringIO()
            with patch.object(module, "_load_backend", return_value=(FakeModel, FakeTorch, FakeTorchaudio)), patch.object(module, "sys") as fake_sys:
                fake_sys.stdin = stdin
                fake_sys.stdout = stdout
                fake_sys.stderr = stderr
                fake_sys.argv = ["stable_audio.py", "generate"]
                result = module.main()
            self.assertEqual(result, 0)
            parsed = json.loads(stdout.getvalue().decode("utf-8"))
            self.assertEqual(parsed["status"], "completed")
            self.assertIn("official progress on stdout", stderr.getvalue())

    def test_wrapper_uses_offline_environment_and_official_python_api(self) -> None:
        source = WRAPPER.read_text(encoding="utf-8")
        for fragment in (
            "HF_HUB_OFFLINE",
            "TRANSFORMERS_OFFLINE",
            "local_files_only=True",
            "from stable_audio_3 import StableAudioModel",
            "StableAudioModel.from_pretrained",
            "inpaint_mask_start_seconds",
            "inpaint_mask_end_seconds",
        ):
            self.assertIn(fragment, source)
        for forbidden in ("stable_audio" + "_tools", "get_pretrained_model", "generate_diffusion_cond"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
