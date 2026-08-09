from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests._bootstrap import ROOT

from game_visual_forge.contracts.video import VideoGenerationMode
from game_visual_forge.contracts.video_provider import VideoModelSupport, VideoProviderBackend
from game_visual_forge.providers.minimax_video import MiniMaxAdapter, build_minimax_submit_request


class FakeTransport:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def request(self, method, path, *, body=None, headers=None):
        self.calls.append((method, path, body, headers))
        return self.payload


class MiniMaxProviderTests(unittest.TestCase):
    def test_h3_uses_v2_content_array(self) -> None:
        request = build_minimax_submit_request(model="MiniMax-H3", mode=VideoGenerationMode.I2V_FIRST, prompt="walk", first_frame_url="memory://prepared/first", duration=6)
        self.assertEqual(request.endpoint, "/v2/video_generation")
        self.assertEqual(request.body["model"], "MiniMax-H3")
        self.assertIsInstance(request.body["content"], list)

    def test_models_snapshot_exposes_unknown_model_without_api_submission(self) -> None:
        transport = FakeTransport({"data": [{"id": "MiniMax-H3"}, {"id": "MiniMax-Future"}]})
        adapter = MiniMaxAdapter(region="global", transport=transport)
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}, clear=False):
            snapshot = adapter.models()
        self.assertEqual(snapshot.model("MiniMax-Future").support, VideoModelSupport.DISCOVERED_UNPROFILED)
        with self.assertRaisesRegex(ValueError, "unprofiled"):
            adapter.prepare(snapshot, "MiniMax-Future", VideoGenerationMode.T2V, {"prompt": "walk"})
        self.assertEqual([call[0] for call in transport.calls], ["GET"])

    def test_api_submit_uses_current_h3_endpoint_and_sanitized_receipt(self) -> None:
        transport = FakeTransport({"task_id": "task-1", "status": "submitted"})
        adapter = MiniMaxAdapter(region="global", transport=transport)
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}, clear=False):
            receipt = adapter.submit({"model": "MiniMax-H3", "prompt": "walk", "duration": 6})
        self.assertEqual(receipt["external_task_id"], "task-1")
        self.assertNotIn("test-key", json.dumps(receipt))
        self.assertEqual(transport.calls[0][1], "/v2/video_generation")

    def test_cli_preflight_does_not_read_credential_file(self) -> None:
        adapter = MiniMaxAdapter(region="global", transport=FakeTransport({}))
        result = adapter.preflight_cli(Path("mmx"), runner=lambda argv: (0, "mmx 1.0", ""))
        self.assertTrue(result["available"])
        self.assertNotIn("credential", json.dumps(result).lower())


if __name__ == "__main__":
    unittest.main()
