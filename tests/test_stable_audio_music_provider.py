import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from tests._bootstrap import ROOT  # noqa: F401
from game_visual_forge.contracts.music_provider import MusicProviderCapability, MusicHttpResponse
from game_visual_forge.providers.stable_audio_music import preflight, submit, query, download, STABLE_AUDIO_3_SUBMIT


class Transport:
    def __init__(self, responses): self.responses = list(responses); self.calls = []
    def __call__(self, method, url, headers, body):
        self.calls.append((method, url, headers, body))
        response = self.responses.pop(0)
        if isinstance(response, Exception): raise response
        return response


def response(code, value=b""):
    return MusicHttpResponse(code, {"content-type": "application/json"}, value if isinstance(value, bytes) else json.dumps(value).encode())


class StableAudioProviderTests(unittest.TestCase):
    def test_preflight_rejects_lyrics_and_accepts_instrumental(self):
        self.assertEqual(preflight({"duration": 1, "lyrics": "hello", "vocal_policy": "vocals-required"})["status"], "unsupported")
        self.assertEqual(preflight({"duration": 380, "prompt": "instrumental"})["status"], "ready")
        self.assertEqual(preflight({"duration": 381})["status"], "unsupported")

    def test_submit_uses_only_official_3_endpoint_and_202_id(self):
        transport = Transport([response(202, {"id": "task-1"})])
        receipt = submit({"prompt": "instrumental", "duration": 1, "output_format": "wav", "credential": "test-token"}, transport)
        self.assertEqual(receipt.external_task_id, "task-1")
        self.assertEqual(transport.calls[0][0:2], ("POST", STABLE_AUDIO_3_SUBMIT))
        self.assertIn(b"stable-audio-3", transport.calls[0][3])

    def test_query_202_does_not_post_and_download_hashes_audio(self):
        transport = Transport([response(202, {"id": "task-1"}), response(200, b"RIFFaudio")])
        cap = MusicProviderCapability.from_dict({"provider": "stable-audio-api", "model": "stable-audio-3", "official_source": "x", "verified_at": "2026-10-10", "is_paid": True, "available": True, "schema_verified": True, "auth_verified": True, "rights_status": "ok", "duration_bounds": [1, 380], "vocal_modes": ["instrumental"], "output_formats": ["wav"], "submission_mode": "async", "id_recovery": True, "pricing_status": "dated"})
        self.assertEqual(query("task-1", cap, transport).status, "running")
        with tempfile.TemporaryDirectory() as temp:
            files = download("task-1", cap, Path(temp), transport)
            self.assertEqual(files[0].sha256, hashlib.sha256(b"RIFFaudio").hexdigest())
            self.assertTrue(Path(files[0].path).exists())
        self.assertEqual([call[0] for call in transport.calls], ["GET", "GET"])

    def test_404_is_expired_and_does_not_retry(self):
        transport = Transport([response(404, {"error": "expired"})])
        with self.assertRaisesRegex(RuntimeError, "expired"):
            query("task-1", None, transport)
        self.assertEqual(len(transport.calls), 1)


if __name__ == "__main__": unittest.main()
