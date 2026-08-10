from __future__ import annotations

import json
import hashlib
import io
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from tests._bootstrap import ROOT

from game_visual_forge.contracts.video import VideoGenerationMode
from game_visual_forge.contracts.video_provider import VideoModelSupport, VideoProviderBackend
from game_visual_forge.providers.minimax_video import MiniMaxAdapter, build_minimax_submit_request, main, run_command


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
        destination.write_bytes(b"h3-video")
        self.downloads.append((url, destination))
        return destination


class Utf8Input(io.StringIO):
    def __init__(self, value: str):
        super().__init__("")
        self.buffer = io.BytesIO(value.encode("utf-8"))


class MiniMaxProviderTests(unittest.TestCase):
    def test_h3_t2v_uses_exact_v2_body_without_legacy_fields(self) -> None:
        request = build_minimax_submit_request(
            model="MiniMax-H3", mode=VideoGenerationMode.T2V,
            prompt="walk", duration=5, resolution="2K", ratio="16:9",
        )
        self.assertEqual(request.endpoint, "/v2/video_generation")
        self.assertEqual(request.body, {
            "model": "MiniMax-H3",
            "content": [{"type": "text", "text": "walk"}],
            "resolution": "2K",
            "duration": 5,
            "ratio": "16:9",
            "aigc_watermark": False,
        })
        self.assertNotIn("prompt", request.body)
        self.assertNotIn("mode", request.body)

    def test_h3_i2v_places_role_on_content_item_and_normalizes_ratio(self) -> None:
        request = build_minimax_submit_request(
            model="MiniMax-H3", mode=VideoGenerationMode.I2V_FIRST,
            prompt="walk", first_frame_url="https://example.invalid/first.png",
            duration=6, resolution="768P", ratio="16:9",
        )
        self.assertEqual(request.body["content"][1], {
            "type": "image_url",
            "image_url": {"url": "https://example.invalid/first.png"},
            "role": "first_frame",
        })
        self.assertEqual(request.body["ratio"], "adaptive")

    def test_h3_reference_mode_builds_multimodal_content(self) -> None:
        request = build_minimax_submit_request(
            model="MiniMax-H3", mode=VideoGenerationMode.REFERENCE_TO_VIDEO,
            prompt="match the action and rhythm", duration=7, resolution="2K",
            ratio="adaptive",
            reference_image_urls=("https://example.invalid/reference.png",),
            reference_video_urls=("https://example.invalid/reference.mp4",),
            reference_audio_urls=("https://example.invalid/reference.mp3",),
        )
        self.assertEqual([item["role"] for item in request.body["content"][1:]], [
            "reference_image", "reference_video", "reference_audio",
        ])

    def test_h3_rejects_invalid_mode_inputs_before_transport(self) -> None:
        with self.assertRaisesRegex(ValueError, "concrete ratio"):
            build_minimax_submit_request(
                model="MiniMax-H3", mode=VideoGenerationMode.T2V,
                prompt="walk", duration=5, resolution="2K", ratio="adaptive",
            )
        with self.assertRaisesRegex(ValueError, "first_frame_url"):
            build_minimax_submit_request(
                model="MiniMax-H3", mode=VideoGenerationMode.I2V_FIRST,
                prompt="walk", duration=5, resolution="2K", ratio="adaptive",
            )

    def test_models_snapshot_exposes_unknown_model_without_api_submission(self) -> None:
        transport = FakeTransport({"data": [{"id": "MiniMax-H3"}, {"id": "MiniMax-Future"}]})
        adapter = MiniMaxAdapter(region="global", transport=transport)
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}, clear=False):
            snapshot = adapter.models()
        h3 = snapshot.model("MiniMax-H3")
        self.assertEqual(h3.durations, tuple(range(4, 16)))
        self.assertEqual(h3.resolutions, ("768P", "2K"))
        self.assertEqual(h3.aspect_ratios, ("adaptive", "21:9", "16:9", "4:3", "1:1", "3:4", "9:16"))
        self.assertEqual(h3.reference_roles, ("first_frame", "last_frame", "reference_image", "reference_video", "reference_audio"))
        self.assertTrue(h3.audio_supported)
        self.assertEqual(snapshot.model("MiniMax-Future").support, VideoModelSupport.DISCOVERED_UNPROFILED)
        with self.assertRaisesRegex(ValueError, "unprofiled"):
            adapter.prepare(snapshot, "MiniMax-Future", VideoGenerationMode.T2V, {"prompt": "walk"})
        self.assertEqual([call[0] for call in transport.calls], ["GET"])

    def test_h3_profile_remains_available_when_discovery_omits_video_models(self) -> None:
        transport = FakeTransport({"data": [{"id": "MiniMax-Future"}]})
        adapter = MiniMaxAdapter(region="global", transport=transport)
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}, clear=False):
            snapshot = adapter.models()
        self.assertEqual(snapshot.model("MiniMax-H3").support, VideoModelSupport.PROFILED)

    def test_prepare_validates_h3_parameters_without_submission(self) -> None:
        transport = FakeTransport({"data": []})
        adapter = MiniMaxAdapter(region="global", transport=transport)
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}, clear=False):
            snapshot = adapter.models()
        with self.assertRaisesRegex(ValueError, "concrete ratio"):
            adapter.prepare(snapshot, "MiniMax-H3", VideoGenerationMode.T2V, {
                "prompt": "walk", "duration": 5, "resolution": "2K", "ratio": "adaptive",
            })
        self.assertEqual([call[0] for call in transport.calls], ["GET"])

    def test_api_submit_uses_current_h3_endpoint_and_sanitized_receipt(self) -> None:
        transport = FakeTransport({"task_id": "task-1", "status": "submitted"})
        adapter = MiniMaxAdapter(region="global", transport=transport)
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}, clear=False):
            receipt = adapter.submit({
                "model": "MiniMax-H3", "mode": "t2v",
                "parameters": {"prompt": "walk", "duration": 5, "resolution": "2K", "ratio": "16:9"},
            })
        self.assertEqual(receipt["external_task_id"], "task-1")
        self.assertNotIn("test-key", json.dumps(receipt))
        self.assertEqual(transport.calls[0][1], "/v2/video_generation")
        self.assertEqual(transport.calls[0][2]["resolution"], "2K")

    def test_i2v_submit_encodes_verified_local_png_without_leaking_receipt(self) -> None:
        transport = FakeTransport({"task_id": "task-i2v", "status": "submitted"})
        adapter = MiniMaxAdapter(region="cn", transport=transport)
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            first_frame = Path(directory) / "first-frame.png"
            png_bytes = b"\x89PNG\r\n\x1a\nverified-first-frame"
            first_frame.write_bytes(png_bytes)
            relative = first_frame.relative_to(ROOT).as_posix()
            digest = hashlib.sha256(png_bytes).hexdigest()
            prepared = {
                "model": "MiniMax-H3",
                "parameters": {
                    "generation_mode": "i2v-first",
                    "first_frame_path": relative,
                    "first_frame_sha256": digest,
                    "prompt": "dash slash",
                    "duration": 5,
                    "resolution": "2K",
                    "ratio": "adaptive",
                },
            }
            with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}, clear=False):
                receipt = adapter.submit(prepared)
        body = transport.calls[0][2]
        first_frame_url = body["content"][1]["image_url"]["url"]
        self.assertTrue(first_frame_url.startswith("data:image/png;base64,"))
        self.assertEqual(body["content"][1]["role"], "first_frame")
        self.assertNotIn("base64", json.dumps(receipt).lower())
        self.assertNotIn(first_frame_url, json.dumps(receipt))

    def test_i2v_submit_rejects_changed_first_frame_before_transport(self) -> None:
        transport = FakeTransport({"task_id": "must-not-submit"})
        adapter = MiniMaxAdapter(region="cn", transport=transport)
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            first_frame = Path(directory) / "first-frame.png"
            first_frame.write_bytes(b"\x89PNG\r\n\x1a\nchanged")
            prepared = {
                "model": "MiniMax-H3", "mode": "i2v-first",
                "parameters": {
                    "first_frame_path": first_frame.relative_to(ROOT).as_posix(),
                    "first_frame_sha256": "0" * 64,
                    "prompt": "dash slash", "duration": 5,
                    "resolution": "2K", "ratio": "adaptive",
                },
            }
            with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}, clear=False):
                with self.assertRaisesRegex(ValueError, "SHA-256"):
                    adapter.submit(prepared)
        self.assertEqual(transport.calls, [])

    def test_i2v_submit_rejects_absolute_first_frame_path(self) -> None:
        transport = FakeTransport({"task_id": "must-not-submit"})
        adapter = MiniMaxAdapter(region="cn", transport=transport)
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            first_frame = Path(directory) / "first-frame.png"
            first_frame.write_bytes(b"\x89PNG\r\n\x1a\nframe")
            prepared = {
                "model": "MiniMax-H3", "mode": "i2v-first",
                "parameters": {
                    "first_frame_path": str(first_frame.resolve()),
                    "first_frame_sha256": hashlib.sha256(first_frame.read_bytes()).hexdigest(),
                    "prompt": "dash slash", "duration": 5,
                    "resolution": "2K", "ratio": "adaptive",
                },
            }
            with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}, clear=False):
                with self.assertRaisesRegex(ValueError, "repository-relative"):
                    adapter.submit(prepared)
        self.assertEqual(transport.calls, [])

    def test_h3_query_uses_v2_task_object_and_sanitizes_result_url(self) -> None:
        result_url = "https://cdn.example.invalid/signed-output.mp4"
        transport = FakeTransport({"task": {"id": "task-1", "status": "succeeded", "content": {"url": result_url}, "resolution": "2K", "duration": 5, "ratio": "16:9"}})
        adapter = MiniMaxAdapter(region="cn", transport=transport)
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}, clear=False):
            receipt = adapter.query("task-1")
        self.assertEqual(transport.calls[0][1], "/v2/query/video_generation/task-1")
        self.assertEqual(receipt["status"], "succeeded")
        self.assertEqual(receipt["resolution"], "2K")
        self.assertNotIn(result_url, json.dumps(receipt))

    def test_h3_download_queries_then_streams_succeeded_result(self) -> None:
        result_url = "https://cdn.example.invalid/output.mp4"
        transport = FakeTransport({"task": {"id": "task-1", "status": "succeeded", "content": {"url": result_url}}})
        adapter = MiniMaxAdapter(region="global", transport=transport)
        with tempfile.TemporaryDirectory(dir=ROOT) as directory, patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}, clear=False):
            output_path = Path(directory) / "download.tmp"
            receipt = adapter.download("task-1", output_path)
            self.assertEqual(output_path.read_bytes(), b"h3-video")
        self.assertEqual(transport.downloads[0][0], result_url)
        self.assertEqual(receipt["path"], str(output_path))
        self.assertNotIn(result_url, json.dumps(receipt))

    def test_h3_download_rejects_unfinished_task(self) -> None:
        adapter = MiniMaxAdapter(region="global", transport=FakeTransport({"task": {"id": "task-1", "status": "running"}}))
        with tempfile.TemporaryDirectory(dir=ROOT) as directory, patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "not succeeded"):
                adapter.download("task-1", Path(directory) / "download.tmp")

    def test_run_command_wires_download_operation(self) -> None:
        transport = FakeTransport({"task": {"id": "task-1", "status": "succeeded", "content": {"url": "https://cdn.example.invalid/output.mp4"}}})
        with tempfile.TemporaryDirectory(dir=ROOT) as directory, patch("game_visual_forge.providers.minimax_video._UrllibTransport", return_value=transport), patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}, clear=False):
            output_path = Path(directory) / "download.tmp"
            receipt = run_command("download", {"region": "cn", "external_task_id": "task-1", "output_path": str(output_path)})
        self.assertEqual(receipt["path"], str(output_path))

    def test_run_command_uses_official_cn_base_url_by_default(self) -> None:
        transport = FakeTransport({})
        with patch("game_visual_forge.providers.minimax_video._UrllibTransport", return_value=transport) as transport_type:
            run_command("capabilities", {"region": "cn", "backend": "api"})
        transport_type.assert_called_once_with("https://api.minimaxi.com")

    def test_cli_returns_sanitized_receipt_for_definite_http_rejection(self) -> None:
        body = io.BytesIO(json.dumps({
            "error": {
                "type": "bad_request_error",
                "message": "invalid video request (2013)",
                "http_code": "400",
            },
            "request_id": "must-not-persist",
        }).encode("utf-8"))
        error = urllib.error.HTTPError(
            "https://api.minimaxi.com/v2/video_generation", 400,
            "Bad Request", {}, body,
        )
        stdin = io.StringIO("{}")
        stdout = io.StringIO()
        with patch("game_visual_forge.providers.minimax_video.run_command", side_effect=error), patch.object(sys, "stdin", stdin), patch.object(sys, "stdout", stdout):
            self.assertEqual(main(["submit"]), 0)
        receipt = json.loads(stdout.getvalue())
        self.assertEqual(receipt["status"], "rejected")
        self.assertEqual(receipt["http_status"], 400)
        self.assertEqual(receipt["error_code"], "2013")
        self.assertNotIn("request_id", receipt)

    def test_cli_returns_sanitized_diagnostic_for_unknown_submit_error(self) -> None:
        stdin = io.StringIO("{}")
        stdout = io.StringIO()
        with patch("game_visual_forge.providers.minimax_video.run_command", side_effect=ConnectionResetError("connection reset by peer")), patch.object(sys, "stdin", stdin), patch.object(sys, "stdout", stdout):
            self.assertEqual(main(["submit"]), 0)
        receipt = json.loads(stdout.getvalue())
        self.assertEqual(receipt["status"], "transport_unknown")
        self.assertEqual(receipt["error_type"], "ConnectionResetError")
        self.assertEqual(receipt["message"], "connection reset by peer")

    def test_cli_reads_non_ascii_payload_from_explicit_utf8_bytes(self) -> None:
        prompt = "right-hand continuity — 0.0–0.8 seconds"
        stdin = Utf8Input(json.dumps({"prompt": prompt}, ensure_ascii=False))
        stdout = io.StringIO()
        with patch("game_visual_forge.providers.minimax_video.run_command", side_effect=lambda command, payload: {"schema_version": 1, "prompt": payload["prompt"]}), patch.object(sys, "stdin", stdin), patch.object(sys, "stdout", stdout):
            self.assertEqual(main(["prepare"]), 0)
        self.assertEqual(json.loads(stdout.getvalue())["prompt"], prompt)

    def test_cli_preflight_does_not_read_credential_file(self) -> None:
        adapter = MiniMaxAdapter(region="global", transport=FakeTransport({}))
        result = adapter.preflight_cli(Path("mmx"), runner=lambda argv: (0, "mmx 1.0", ""))
        self.assertTrue(result["available"])
        self.assertNotIn("credential", json.dumps(result).lower())


if __name__ == "__main__":
    unittest.main()
