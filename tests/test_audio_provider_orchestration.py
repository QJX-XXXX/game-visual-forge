from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from tests._bootstrap import ROOT  # noqa: F401
from tests.test_audio_contract import valid_audio_request

from game_visual_forge.contracts.audio import AudioRequest
from game_visual_forge.contracts.audio_provider import AudioAttemptStatus
from game_visual_forge.providers.audio import generate_audio_candidates, run_audio_provider_models, run_audio_provider_preflight


FAKE = ROOT / "tests" / "fixtures" / "fake_audio_provider.py"
NOW = "2026-08-14T00:00:00Z"


class AudioProviderOrchestrationTests(unittest.TestCase):
    def test_preflight_and_models_use_binary_utf8_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "日志.txt"
            payload = {"log_path": str(log), "prompt": "中文路径"}
            preflight = run_audio_provider_preflight(FAKE, payload)
            self.assertTrue(preflight.model_local)
            self.assertEqual(run_audio_provider_models(FAKE, payload)["models"], ["small-sfx"])
            self.assertEqual(log.read_text(encoding="utf-8").splitlines(), ["preflight", "models"])

    def test_explicit_interpreter_and_child_environment_do_not_mutate_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / "env.json"
            payload = {"env_log_path": str(log)}
            parent_marker = os.environ.get("GVF_TEST_CHILD")
            child_env = os.environ.copy()
            child_env["GVF_TEST_CHILD"] = "中文值"
            run_audio_provider_models(FAKE, payload, python_executable=Path(sys.executable), environment=child_env)
            record = json.loads(log.read_text(encoding="utf-8"))
            self.assertEqual(record["python"], str(Path(sys.executable)))
            self.assertEqual(record["environment"]["GVF_TEST_CHILD"], "中文值")
            self.assertEqual(os.environ.get("GVF_TEST_CHILD"), parent_marker)

    def test_three_text_candidates_have_distinct_seeds_and_round_trip_unicode(self) -> None:
        request = AudioRequest.from_dict(valid_audio_request(prompt="中文 sword impact"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = generate_audio_candidates(request, root / "attempts", FAKE, root / "output", None, NOW)
            self.assertEqual(len(result.candidates), 3)
            self.assertEqual(len({candidate.seed for candidate in result.candidates}), 3)
            self.assertTrue((root / "output" / "raw" / "candidate-01.wav").is_file())
            attempts = [json.loads(Path(path).read_text(encoding="utf-8")) for path in result.attempt_paths]
            self.assertTrue(all(item["status"] == "completed" for item in attempts))

    def test_nonzero_exit_is_failed_and_not_retried(self) -> None:
        request = AudioRequest.from_dict(valid_audio_request())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wrapper = root / "failed.py"
            wrapper.write_text(
                "import sys; sys.stdin.buffer.read(); sys.stderr.write('failed'); sys.exit(9)",
                encoding="utf-8",
            )
            result = generate_audio_candidates(request, root / "attempts", wrapper, root / "output", None, NOW)
            self.assertEqual(result.candidates, ())
            attempts = [json.loads(Path(path).read_text(encoding="utf-8")) for path in result.attempt_paths]
            statuses = [attempt["status"] for attempt in attempts]
            self.assertEqual(statuses, ["failed", "failed", "failed"])
            for attempt in attempts:
                failure = attempt["parameters"]["failure"]
                self.assertEqual(failure["code"], "provider_unavailable")
                self.assertEqual(failure["message"], "audio provider command failed")
                self.assertEqual(failure["context"]["returncode"], 9)
                self.assertEqual(failure["context"]["stderr"], "failed")

    def test_invalid_utf8_is_generation_unknown_and_not_retried(self) -> None:
        request = AudioRequest.from_dict(valid_audio_request())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            class InvalidUtf8Provider:
                pass
            # The provider fixture reads this marker from an environment-independent payload.
            # Use a temporary wrapper so the normal binary protocol remains under test.
            wrapper = root / "invalid.py"
            wrapper.write_text(
                "import sys; sys.stdin.buffer.read(); sys.stdout.buffer.write(b'\\xff\\xfe'); sys.exit(0)",
                encoding="utf-8",
            )
            result = generate_audio_candidates(request, root / "attempts", wrapper, root / "output", None, NOW)
            self.assertEqual(result.candidates, ())
            statuses = [json.loads(Path(path).read_text(encoding="utf-8"))["status"] for path in result.attempt_paths]
            self.assertEqual(statuses, [AudioAttemptStatus.GENERATION_UNKNOWN.value] * 3)


if __name__ == "__main__":
    unittest.main()
