from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests._bootstrap import ROOT

from game_visual_forge.contracts.video import VideoGenerationMode
from game_visual_forge.providers.jimeng_video import (
    JIMENG_PRO_MODEL,
    VOLCENGINE_QUERY_ACTION,
    VOLCENGINE_SUBMIT_ACTION,
    JimengAdapter,
    _action_path,
    main,
    sign_volcengine_request,
)


class FakeTransport:
    def __init__(self, payloads):
        self.payloads = list(payloads) if isinstance(payloads, list) else [payloads]
        self.calls = []
        self.downloads = []

    def request(self, method, path, *, body=None, headers=None):
        self.calls.append((method, path, body, headers))
        return self.payloads.pop(0)

    def download(self, url, path):
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"jimeng-video")
        self.downloads.append((url, destination))
        return destination


class JimengProviderTests(unittest.TestCase):
    def test_api_signature_uses_volcengine_v4_fields(self) -> None:
        signed = sign_volcengine_request(
            method="POST",
            url=_action_path(VOLCENGINE_SUBMIT_ACTION),
            headers={"Content-Type": "application/json"},
            body={"prompt": "walk", "req_key": JIMENG_PRO_MODEL},
            access_key="AKIDEXAMPLE",
            secret_key="secret",
            now="2026-08-09T00:00:00Z",
        )
        self.assertTrue(signed.authorization.startswith("HMAC-SHA256 Credential=AKIDEXAMPLE/20260809/cn-north-1/cv/request"))
        self.assertIn("SignedHeaders=content-type;host;x-content-sha256;x-date", signed.authorization)
        self.assertEqual(signed.headers["X-Date"], "20260809T000000Z")
        self.assertEqual(signed.headers["Host"], "visual.volcengineapi.com")

    def test_api_submit_uses_action_endpoint_and_sanitized_receipt(self) -> None:
        transport = FakeTransport({"code": 10000, "data": {"task_id": "jimeng-1"}})
        adapter = JimengAdapter(transport=transport)
        with patch.dict(os.environ, {"JIMENG_ACCESS_KEY": "ak", "JIMENG_SECRET_KEY": "secret"}, clear=False):
            receipt = adapter.submit({"model": JIMENG_PRO_MODEL, "mode": "t2v", "parameters": {"prompt": "walk", "frames": 121}})
        self.assertEqual(receipt["external_task_id"], "jimeng-1")
        self.assertNotIn("secret", json.dumps(receipt))
        self.assertEqual(transport.calls[0][0:2], ("POST", _action_path(VOLCENGINE_SUBMIT_ACTION)))
        self.assertEqual(transport.calls[0][2]["req_key"], JIMENG_PRO_MODEL)
        self.assertEqual(transport.calls[0][3]["Region"], "cn-north-1")
        self.assertEqual(transport.calls[0][3]["Service"], "cv")

    def test_models_are_static_official_profiles(self) -> None:
        adapter = JimengAdapter(transport=FakeTransport({}))
        snapshot = adapter.models()
        self.assertEqual(snapshot.adapter_version, "2.0")
        self.assertIn(JIMENG_PRO_MODEL, {item.model for item in snapshot.models})
        self.assertEqual(snapshot.model(JIMENG_PRO_MODEL).durations, (5, 10))

    def test_query_and_download_use_action_endpoint_and_video_url(self) -> None:
        transport = FakeTransport([
            {"code": 10000, "data": {"status": "done", "video_url": "https://cdn.example.invalid/video.mp4"}},
            {"code": 10000, "data": {"status": "done", "video_url": "https://cdn.example.invalid/video.mp4"}},
        ])
        adapter = JimengAdapter(transport=transport)
        with patch.dict(os.environ, {"JIMENG_ACCESS_KEY": "ak", "JIMENG_SECRET_KEY": "secret"}, clear=False):
            receipt = adapter.query("task-1", model=JIMENG_PRO_MODEL)
            with tempfile.TemporaryDirectory(dir=ROOT) as directory:
                downloaded = adapter.download("task-1", Path(directory) / "video.mp4", model=JIMENG_PRO_MODEL)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(downloaded["status"], "downloaded")
        self.assertEqual(transport.calls[0][0:2], ("POST", _action_path(VOLCENGINE_QUERY_ACTION)))
        self.assertEqual(transport.calls[0][2], {"req_key": JIMENG_PRO_MODEL, "task_id": "task-1"})
        self.assertNotIn("video_url", json.dumps(receipt))

    def test_cli_and_api_task_recovery_are_separate(self) -> None:
        attempt = {"provider": "jimeng", "backend": "api", "external_task_id": "api-1"}
        with self.assertRaisesRegex(ValueError, "backend"):
            JimengAdapter(transport=FakeTransport({})).query_cli_attempt(attempt, Path("dreamina"), runner=lambda argv: (0, "ok", ""))

    def test_cli_preflight_uses_version_only(self) -> None:
        result = JimengAdapter(transport=FakeTransport({})).preflight_cli(Path("dreamina"), runner=lambda argv: (0, "dreamina 1.0", ""))
        self.assertTrue(result["available"])
        self.assertEqual(result["backend"], "cli")

    def test_main_round_trips_unicode_through_shared_binary_protocol(self) -> None:
        source = io.BytesIO('{"schema_version":1,"prompt":"白发少女三连斩"}'.encode("utf-8"))
        target = io.BytesIO()
        with patch(
            "game_visual_forge.providers.jimeng_video.run_command",
            return_value={"schema_version": 1, "message": "提交成功"},
        ):
            self.assertEqual(main(["preflight"], source, target), 0)
        self.assertEqual(json.loads(target.getvalue().decode("utf-8"))["message"], "提交成功")


if __name__ == "__main__":
    unittest.main()
