import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from tests._bootstrap import ROOT  # noqa: F401
from tests.test_music_contract import music_request
from game_visual_forge.contracts.music import build_music_prompt_package
from game_visual_forge.contracts.music_provider import MusicProvider, MusicPaidConfirmation, MusicProviderReceipt, default_music_capabilities
from game_visual_forge.contracts.serialization import dump_json, load_json
from game_visual_forge.providers.music import prepare_music_attempt, begin_music_submission, record_music_receipt, submit_cloud_music_attempt, query_cloud_music_attempt

NOW = "2026-10-10T00:00:00Z"


def attempt(paid=True):
    cap = default_music_capabilities(local_ready=True)[MusicProvider.STABLE_AUDIO_API if paid else MusicProvider.COMFYUI_MUSIC3]
    cap = replace(cap, auth_verified=True)
    request = music_request()
    return prepare_music_attempt(request, build_music_prompt_package(request, cap.provider, request.brief), cap, {"seed": 1}, now=NOW)


class MusicOrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "attempt.json"
        self.confirmation = self.path.with_name("confirmation.json")
        self.attempt = attempt()
        dump_json(self.path, self.attempt.to_dict())

    def authorize(self):
        dump_json(self.confirmation, MusicPaidConfirmation.for_attempt(self.attempt, confirmed_at=NOW).to_dict())

    def test_paid_confirmation_required_bound_and_consumed(self):
        with self.assertRaisesRegex(ValueError, "confirmation"):
            begin_music_submission(self.path, None, now=NOW)
        self.authorize()
        before = load_json(self.confirmation)
        for field in ["provider", "model", "capability_sha256", "generation_fingerprint", "parameters_sha256", "submission_count", "expected_candidate_count", "estimated_credits"]:
            modified = dict(before)
            modified[field] = "wrong" if isinstance(modified[field], str) else 999
            dump_json(self.confirmation, modified)
            with self.subTest(field=field), self.assertRaises(ValueError):
                begin_music_submission(self.path, self.confirmation, now=NOW)
        dump_json(self.confirmation, before)
        result = begin_music_submission(self.path, self.confirmation, now=NOW)
        self.assertEqual(result.status, "submitting")
        self.assertTrue(load_json(self.confirmation)["consumed"])
        with self.assertRaises(ValueError):
            begin_music_submission(self.path, self.confirmation, now=NOW)

    def test_local_does_not_require_confirmation(self):
        dump_json(self.path, attempt(False).to_dict())
        self.assertEqual(begin_music_submission(self.path, None, now=NOW).status, "submitting")

    def test_unknown_receipt_never_resubmits(self):
        self.authorize()
        begin_music_submission(self.path, self.confirmation, now=NOW)
        result = record_music_receipt(self.path, MusicProviderReceipt("submission_unknown"), now=NOW)
        self.assertEqual(result.status, "submission_unknown")
        with self.assertRaises(ValueError):
            begin_music_submission(self.path, self.confirmation, now=NOW)
        with self.assertRaises(ValueError):
            query_cloud_music_attempt(self.path, Path("fake.py"), now=NOW)

    def test_transport_failures_persist_unknown(self):
        for error in [TimeoutError(), UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad"), ValueError("bad json")]:
            self.attempt = attempt()
            dump_json(self.path, self.attempt.to_dict())
            self.authorize()
            with patch("game_visual_forge.providers.music._provider_call", side_effect=error):
                result = submit_cloud_music_attempt(self.path, self.confirmation, Path("fake.py"), now=NOW)
            self.assertEqual(result.status, "submission_unknown")

    def test_id_recovers_by_query_only(self):
        self.authorize()
        begin_music_submission(self.path, self.confirmation, now=NOW)
        record_music_receipt(self.path, MusicProviderReceipt("submitted", "id-1"), now=NOW)
        with patch("game_visual_forge.providers.music._provider_call", return_value={"status": "running", "external_task_id": "id-1"}) as call:
            result = query_cloud_music_attempt(self.path, Path("fake.py"), now=NOW)
        self.assertEqual(result.status, "running")
        self.assertEqual(call.call_args.args[1]["operation"], "query")
        self.assertEqual(result.external_task_id, "id-1")


if __name__ == "__main__":
    unittest.main()
