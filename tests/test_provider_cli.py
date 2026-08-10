from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from tests._bootstrap import ROOT  # noqa: F401
from game_visual_forge.contracts import CostEstimate, ExternalProvider, PaidConfirmation, ProviderCommand
from game_visual_forge.errors import ErrorCode, ForgeError
from game_visual_forge.providers import run_provider_command, submit_provider_command


FAKE = ROOT / "tests" / "fixtures" / "fake_provider.py"
UTF8_FAKE = ROOT / "tests" / "fixtures" / "fake_utf8_provider.py"


class ProviderCliTests(unittest.TestCase):
    def test_all_non_submit_commands_return_versioned_json(self) -> None:
        for command in (ProviderCommand.CAPABILITIES, ProviderCommand.PREFLIGHT, ProviderCommand.ESTIMATE, ProviderCommand.PREPARE, ProviderCommand.QUERY, ProviderCommand.DOWNLOAD):
            with self.subTest(command=command):
                result = run_provider_command(FAKE, command, {"schema_version": 1, "provider": "dreamina"})
                self.assertEqual(result["schema_version"], 1)

    def test_submit_requires_confirmation_and_consumed_confirmation(self) -> None:
        estimate = CostEstimate(1, ExternalProvider.DREAMINA, "CNY", "0.50", True, "estimated")
        confirmation = PaidConfirmation.create(
            attempt_id="attempt-001", provider=ExternalProvider.DREAMINA, model="dreamina-image-v1",
            parameters={"width": 1024}, quantity=1, estimate=estimate,
            request_fingerprint="a" * 64, confirmed_at="2026-07-30T01:00:00Z",
        )
        payload = {
            "schema_version": 1, "attempt_id": "attempt-001", "provider": "dreamina",
            "model": "dreamina-image-v1", "parameters": {"width": 1024}, "quantity": 1,
            "estimate": estimate.to_dict(), "request_fingerprint": "a" * 64,
        }
        with self.assertRaisesRegex(ForgeError, "confirmation"):
            run_provider_command(FAKE, ProviderCommand.SUBMIT, payload)
        with self.assertRaisesRegex(ForgeError, "consumed"):
            submit_provider_command(FAKE, payload, confirmation)
        consumed = confirmation.authorize_attempt(
            attempt_id="attempt-001", provider=ExternalProvider.DREAMINA, model="dreamina-image-v1",
            parameters={"width": 1024}, quantity=1, estimate=estimate,
            request_fingerprint="a" * 64, now="2026-07-30T01:01:00Z",
        )
        response = submit_provider_command(FAKE, payload, consumed)
        self.assertEqual(response["status"], "submitted")

    def test_invalid_and_sensitive_provider_output_is_not_exposed(self) -> None:
        for payload, expected in (({"mode": "invalid-json"}, "invalid JSON"), ({"mode": "stdout-secret"}, "sensitive"), ({"mode": "stderr-secret"}, "failed")):
            with self.subTest(mode=payload["mode"]):
                with self.assertRaises(ForgeError) as caught:
                    run_provider_command(FAKE, ProviderCommand.PREFLIGHT, payload)
                self.assertIn(expected, str(caught.exception))
                self.assertNotIn("secret", json.dumps(caught.exception.to_dict()).lower())

    def test_invalid_utf8_stdout_is_recoverable_provider_failure(self) -> None:
        decode_error = UnicodeDecodeError("utf-8", b"\x81", 0, 1, "invalid start byte")
        with patch("game_visual_forge.providers.cli.run_utf8_json_process", side_effect=decode_error):
            with self.assertRaises(ForgeError) as caught:
                run_provider_command(FAKE, ProviderCommand.PREFLIGHT, {"schema_version": 1})
        self.assertEqual(caught.exception.code, ErrorCode.PROVIDER_UNAVAILABLE)
        self.assertTrue(caught.exception.recoverable)

    def test_non_utf8_stderr_does_not_hide_valid_stdout(self) -> None:
        result = run_provider_command(
            UTF8_FAKE,
            ProviderCommand.PREFLIGHT,
            {"schema_version": 1, "fixture_mode": "invalid-stderr"},
        )
        self.assertTrue(result["available"])


if __name__ == "__main__":
    unittest.main()
