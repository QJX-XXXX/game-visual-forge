from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests._bootstrap import ROOT

from game_visual_forge.contracts.provider import CostEstimate, ExternalProvider
from game_visual_forge.contracts.serialization import dump_json, load_json
from game_visual_forge.contracts.video import VideoGenerationMode
from game_visual_forge.contracts.video_provider import VideoAttemptStatus, VideoGenerationAttempt, VideoPaidConfirmation, VideoProviderBackend
from game_visual_forge.errors import ErrorCode
from game_visual_forge.providers.video import download_video_attempt, query_video_attempt, submit_video_attempt


NOW = "2026-08-09T00:00:00Z"
FAKE = ROOT / "tests" / "fixtures" / "fake_video_provider.py"


class VideoProviderOrchestrationTests(unittest.TestCase):
    def setup_paths(self, root: Path):
        attempt_path = root / "attempt.json"
        confirmation_path = root / "confirmation.json"
        log_path = root / "events.log"
        attempt = VideoGenerationAttempt(1, "attempt-1", "b" * 64, ExternalProvider.MINIMAX, VideoProviderBackend.API, "global", "MiniMax-H3", "a" * 64, {"prompt": "walk", "duration": 6}, VideoAttemptStatus.PREPARED, NOW, NOW)
        estimate = CostEstimate(1, ExternalProvider.MINIMAX, "USD", "0.1", True, "verified")
        confirmation = VideoPaidConfirmation.create(attempt_id="attempt-1", provider=ExternalProvider.MINIMAX, backend=VideoProviderBackend.API, region="global", model="MiniMax-H3", model_snapshot_sha256="a" * 64, mode=VideoGenerationMode.T2V, parameters={"prompt": "walk", "duration": 6}, reference_sha256=(), quantity=1, estimate=estimate, request_fingerprint="b" * 64, confirmed_at=NOW)
        dump_json(attempt_path, attempt.to_dict())
        dump_json(confirmation_path, confirmation.to_dict())
        return attempt_path, confirmation_path, log_path

    def test_submit_persists_confirmation_before_single_transport_call(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            attempt_path, confirmation_path, log_path = self.setup_paths(root)
            with patch.dict(os.environ, {"GAME_VISUAL_FORGE_FAKE_PROVIDER_LOG": str(log_path)}, clear=False):
                result = submit_video_attempt(attempt_path, confirmation_path, FAKE, now=NOW)
            self.assertEqual(result.status, VideoAttemptStatus.SUBMITTED)
            self.assertEqual(log_path.read_text(encoding="utf-8").splitlines().count("submit"), 1)
            self.assertIsNotNone(load_json(confirmation_path)["consumed_at"])

    def test_unknown_outcome_cannot_be_resubmitted(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            attempt_path, confirmation_path, log_path = self.setup_paths(root)
            unknown = VideoGenerationAttempt.from_dict(load_json(attempt_path)).replace(status=VideoAttemptStatus.SUBMISSION_UNKNOWN, updated_at=NOW)
            dump_json(attempt_path, unknown.to_dict())
            with self.assertRaisesRegex(ValueError, "query"):
                submit_video_attempt(attempt_path, confirmation_path, FAKE, now=NOW)

    def test_definite_provider_rejection_is_failed_not_unknown(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            attempt_path, confirmation_path, _ = self.setup_paths(root)
            receipt = {
                "schema_version": 1,
                "status": "rejected",
                "http_status": 400,
                "error_code": "2013",
                "message": "invalid video request (2013)",
            }
            with patch("game_visual_forge.providers.video._run", return_value=receipt):
                result = submit_video_attempt(attempt_path, confirmation_path, FAKE, now=NOW)
            self.assertEqual(result.status, VideoAttemptStatus.FAILED)
            self.assertEqual(result.error_code, "2013")
            self.assertIsNone(result.external_task_id)
            self.assertIsNotNone(load_json(confirmation_path)["consumed_at"])
            rejection = load_json(attempt_path.with_name("attempt-provider-rejection.json"))
            self.assertEqual(rejection["http_status"], 400)
            self.assertEqual(rejection["message"], "invalid video request (2013)")

    def test_transport_diagnostic_is_persisted_for_unknown_submit(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            attempt_path, confirmation_path, _ = self.setup_paths(root)
            receipt = {
                "schema_version": 1,
                "status": "transport_unknown",
                "error_type": "ConnectionResetError",
                "message": "connection reset by peer",
            }
            with patch("game_visual_forge.providers.video._run", return_value=receipt):
                result = submit_video_attempt(attempt_path, confirmation_path, FAKE, now=NOW)
            self.assertEqual(result.status, VideoAttemptStatus.SUBMISSION_UNKNOWN)
            diagnostic = load_json(attempt_path.with_name("attempt-provider-diagnostic.json"))
            self.assertEqual(diagnostic["error_type"], "ConnectionResetError")
            self.assertEqual(diagnostic["message"], "connection reset by peer")

    def test_invalid_utf8_submit_stdout_becomes_submission_unknown(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            attempt_path, confirmation_path, _ = self.setup_paths(root)
            decode_error = UnicodeDecodeError("utf-8", b"\x81", 0, 1, "invalid start byte")
            with patch("game_visual_forge.providers.video.run_utf8_json_process", side_effect=decode_error):
                result = submit_video_attempt(attempt_path, confirmation_path, FAKE, now=NOW)
            self.assertEqual(result.status, VideoAttemptStatus.SUBMISSION_UNKNOWN)
            self.assertEqual(result.error_code, ErrorCode.SUBMISSION_UNKNOWN.value)

    def test_query_then_atomic_download(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            attempt_path, confirmation_path, log_path = self.setup_paths(root)
            submitted = submit_video_attempt(attempt_path, confirmation_path, FAKE, now=NOW)
            queried = query_video_attempt(attempt_path, FAKE, now=NOW)
            self.assertEqual(queried.status, VideoAttemptStatus.COMPLETED)
            downloaded = download_video_attempt(attempt_path, FAKE, root / "downloads", now=NOW)
            self.assertEqual(downloaded.status, VideoAttemptStatus.DOWNLOADED)
            self.assertTrue((root / "downloads" / "video.mp4").is_file())

    def test_query_preserves_provider_terminal_failure_states(self) -> None:
        cases = {
            "failed": VideoAttemptStatus.FAILED,
            "cancelled": VideoAttemptStatus.CANCELLED,
            "running": VideoAttemptStatus.RUNNING,
        }
        for provider_status, expected in cases.items():
            with self.subTest(provider_status=provider_status), tempfile.TemporaryDirectory(dir=ROOT) as directory:
                root = Path(directory)
                attempt_path, _, _ = self.setup_paths(root)
                attempt = VideoGenerationAttempt.from_dict(load_json(attempt_path)).replace(
                    status=VideoAttemptStatus.SUBMITTED,
                    external_task_id="task-1",
                )
                dump_json(attempt_path, attempt.to_dict())
                receipt = {"schema_version": 1, "external_task_id": "task-1", "status": provider_status}
                with patch("game_visual_forge.providers.video._run", return_value=receipt):
                    result = query_video_attempt(attempt_path, FAKE, now=NOW)
                self.assertEqual(result.status, expected)

    def test_query_and_download_preserve_attempt_region(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            attempt_path, _, _ = self.setup_paths(root)
            attempt = VideoGenerationAttempt.from_dict(load_json(attempt_path)).replace(
                status=VideoAttemptStatus.SUBMITTED,
                external_task_id="task-cn",
            )
            attempt = VideoGenerationAttempt(
                attempt.schema_version, attempt.attempt_id, attempt.request_fingerprint,
                attempt.provider, attempt.backend, "cn", attempt.model,
                attempt.model_snapshot_sha256, attempt.parameters, attempt.status,
                attempt.created_at, attempt.updated_at, attempt.external_task_id,
            )
            dump_json(attempt_path, attempt.to_dict())
            query_receipt = {"schema_version": 1, "external_task_id": "task-cn", "status": "succeeded"}
            with patch("game_visual_forge.providers.video._run", return_value=query_receipt) as provider_run:
                query_video_attempt(attempt_path, FAKE, now=NOW)
            self.assertEqual(provider_run.call_args.args[2]["region"], "cn")

            temporary = root / "downloads" / ".video-download.tmp"
            temporary.parent.mkdir(parents=True)
            temporary.write_bytes(b"video")
            download_receipt = {"schema_version": 1, "external_task_id": "task-cn", "status": "downloaded", "path": str(temporary)}
            with patch("game_visual_forge.providers.video._run", return_value=download_receipt) as provider_run:
                download_video_attempt(attempt_path, FAKE, root / "downloads", now=NOW)
            self.assertEqual(provider_run.call_args.args[2]["region"], "cn")

    def test_i2v_submit_binds_mode_and_first_frame_hash(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            attempt_path = root / "attempt.json"
            confirmation_path = root / "confirmation.json"
            digest = "c" * 64
            parameters = {
                "generation_mode": "i2v-first",
                "first_frame_path": "outputs/run/first-frame.png",
                "first_frame_sha256": digest,
                "reference_sha256": [digest],
                "prompt": "dash slash",
                "duration": 5,
                "resolution": "2K",
                "ratio": "adaptive",
            }
            attempt = VideoGenerationAttempt(
                1, "attempt-i2v", "b" * 64, ExternalProvider.MINIMAX,
                VideoProviderBackend.API, "cn", "MiniMax-H3", "a" * 64,
                parameters, VideoAttemptStatus.PREPARED, NOW, NOW,
            )
            estimate = CostEstimate(1, ExternalProvider.MINIMAX, None, None, False, "unverified")
            confirmation = VideoPaidConfirmation.create(
                attempt_id="attempt-i2v", provider=ExternalProvider.MINIMAX,
                backend=VideoProviderBackend.API, region="cn", model="MiniMax-H3",
                model_snapshot_sha256="a" * 64, mode=VideoGenerationMode.I2V_FIRST,
                parameters=parameters, reference_sha256=(digest,), quantity=1,
                estimate=estimate, request_fingerprint="b" * 64,
                confirmed_at=NOW, estimate_acknowledged=True,
            )
            dump_json(attempt_path, attempt.to_dict())
            dump_json(confirmation_path, confirmation.to_dict())
            receipt = {"schema_version": 1, "external_task_id": "task-i2v", "status": "submitted"}
            with patch("game_visual_forge.providers.video._run", return_value=receipt) as provider_run:
                result = submit_video_attempt(attempt_path, confirmation_path, FAKE, now=NOW)
            self.assertEqual(result.status, VideoAttemptStatus.SUBMITTED)
            payload = provider_run.call_args.args[2]
            self.assertEqual(payload["mode"], "i2v-first")
            self.assertEqual(payload["parameters"]["reference_sha256"], [digest])

    def test_superseded_attempt_cannot_submit(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            attempt_path, confirmation_path, _ = self.setup_paths(root)
            attempt = VideoGenerationAttempt.from_dict(load_json(attempt_path)).replace(
                status=VideoAttemptStatus.SUPERSEDED,
            )
            dump_json(attempt_path, attempt.to_dict())
            with patch("game_visual_forge.providers.video._run") as provider_run:
                with self.assertRaisesRegex(ValueError, "prepared"):
                    submit_video_attempt(attempt_path, confirmation_path, FAKE, now=NOW)
            provider_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
