from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from tests._bootstrap import ROOT

from game_visual_forge.contracts.video_provider import VideoProviderBackend
from game_visual_forge.providers.jimeng_video import JimengAdapter, sign_volcengine_request


class FakeTransport:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def request(self, method, path, *, body=None, headers=None):
        self.calls.append((method, path, body, headers))
        return self.payload


class JimengProviderTests(unittest.TestCase):
    def test_api_signature_is_deterministic(self) -> None:
        signed = sign_volcengine_request(method="POST", url="/api/v1/video/generate", headers={"Content-Type": "application/json"}, body={"prompt": "walk"}, access_key="AKIDEXAMPLE", secret_key="secret", now="2026-08-09T00:00:00Z")
        self.assertEqual(signed.authorization, "HMAC-SHA256 AccessKey=AKIDEXAMPLE, Signature=d610ebd4cc2809b7cf1b9f098d7b8540173dd9105132ff220c9cd1176f7e1e55")

    def test_api_submit_redacts_credentials_from_receipt(self) -> None:
        transport = FakeTransport({"task_id": "jimeng-1", "status": "submitted"})
        adapter = JimengAdapter(transport=transport)
        with patch.dict(os.environ, {"JIMENG_ACCESS_KEY": "ak", "JIMENG_SECRET_KEY": "secret"}, clear=False):
            receipt = adapter.submit({"prompt": "walk", "duration": 5})
        self.assertEqual(receipt["external_task_id"], "jimeng-1")
        self.assertNotIn("secret", json.dumps(receipt))

    def test_cli_and_api_task_recovery_are_separate(self) -> None:
        attempt = {"provider": "jimeng", "backend": "api", "external_task_id": "api-1"}
        with self.assertRaisesRegex(ValueError, "backend"):
            JimengAdapter(transport=FakeTransport({})).query_cli_attempt(attempt, Path("dreamina"), runner=lambda argv: (0, "ok", ""))

    def test_cli_preflight_uses_version_only(self) -> None:
        result = JimengAdapter(transport=FakeTransport({})).preflight_cli(Path("dreamina"), runner=lambda argv: (0, "dreamina 1.0", ""))
        self.assertTrue(result["available"])
        self.assertEqual(result["backend"], "cli")


if __name__ == "__main__":
    unittest.main()
