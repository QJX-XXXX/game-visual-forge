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


if __name__ == "__main__":
    unittest.main()
