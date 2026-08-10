from __future__ import annotations

import io
import json
import subprocess
import sys
import unittest
from unittest.mock import patch

from tests._bootstrap import ROOT

from game_visual_forge.providers.stdio import read_utf8_json, run_utf8_json_process, write_utf8_json


class ProviderStdioTests(unittest.TestCase):
    def test_child_protocol_round_trips_unicode_as_utf8_bytes(self) -> None:
        request = read_utf8_json(io.BytesIO('{"prompt":"白发少女“向右”挥剑—三连斩"}'.encode("utf-8")))
        output = io.BytesIO()
        write_utf8_json({"schema_version": 1, "echo": request["prompt"]}, output)
        self.assertEqual(
            output.getvalue(),
            '{"schema_version":1,"echo":"白发少女“向右”挥剑—三连斩"}\n'.encode("utf-8"),
        )

    def test_child_protocol_rejects_non_object_json(self) -> None:
        with self.assertRaisesRegex(ValueError, "JSON object"):
            read_utf8_json(io.BytesIO(b"[]"))

    def test_child_protocol_retains_text_stream_fallback_for_in_process_tests(self) -> None:
        request = read_utf8_json(io.StringIO('{"prompt":"白发少女"}'))
        output = io.StringIO()
        write_utf8_json({"schema_version": 1, "prompt": request["prompt"]}, output)
        self.assertEqual(json.loads(output.getvalue())["prompt"], "白发少女")

    def test_parent_uses_bytes_and_replaces_invalid_stderr(self) -> None:
        completed = subprocess.CompletedProcess(
            ["provider"], 0, b'{"schema_version":1}\n', b"diagnostic:\x81",
        )
        with patch("game_visual_forge.providers.stdio.subprocess.run", return_value=completed) as run:
            result = run_utf8_json_process(
                ["provider", "preflight"],
                {"prompt": "白发少女"},
                timeout_seconds=30,
            )
        self.assertIsInstance(run.call_args.kwargs["input"], bytes)
        self.assertFalse(run.call_args.kwargs["text"])
        self.assertIn("白发少女".encode("utf-8"), run.call_args.kwargs["input"])
        self.assertEqual(result.stdout, '{"schema_version":1}\n')
        self.assertEqual(result.stderr, "diagnostic:\ufffd")

    def test_parent_rejects_invalid_utf8_stdout(self) -> None:
        completed = subprocess.CompletedProcess(["provider"], 0, b"\x81", b"")
        with patch("game_visual_forge.providers.stdio.subprocess.run", return_value=completed):
            with self.assertRaises(UnicodeDecodeError):
                run_utf8_json_process(["provider"], {}, timeout_seconds=30)

    def test_real_local_subprocess_round_trips_unicode(self) -> None:
        fixture = ROOT / "tests" / "fixtures" / "fake_utf8_provider.py"
        result = run_utf8_json_process(
            [sys.executable, str(fixture), "preflight"],
            {"prompt": "白发少女", "fixture_mode": "invalid-stderr"},
            timeout_seconds=30,
        )
        self.assertEqual(json.loads(result.stdout)["available"], True)
        self.assertEqual(result.stderr, "provider:\ufffd")


if __name__ == "__main__":
    unittest.main()
