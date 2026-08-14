from __future__ import annotations

import sys
import unittest

from tests._bootstrap import ROOT  # noqa: F401
from tests.test_audio_contract import valid_audio_request

from game_visual_forge.contracts.audio import AudioGenerationMode, AudioRequest
from game_visual_forge.contracts.audio_provider import AudioGenerationAttempt, AudioProviderPreflight, AudioAttemptStatus
from game_visual_forge.jobs.fingerprints import fingerprint_request


NOW = "2026-08-14T00:00:00Z"


class AudioProviderContractTests(unittest.TestCase):
    def test_preflight_requires_exact_small_sfx_local_model(self) -> None:
        preflight = AudioProviderPreflight.from_dict({
            "schema_version": 1,
            "provider": "stable-audio-local",
            "available": True,
            "python_executable": sys.executable,
            "package": "stable-audio-3",
            "package_version": "0.1.0",
            "model_id": "small-sfx",
            "model_repository": "stabilityai/stable-audio-3-small-sfx",
            "model_local": True,
            "ffmpeg_available": True,
            "ffprobe_available": True,
            "reason": None,
        })
        self.assertTrue(preflight.available)
        with self.assertRaisesRegex(ValueError, "small-sfx"):
            AudioProviderPreflight.from_dict(preflight.to_dict() | {"model_id": "medium"})

    def test_attempt_cannot_restart_from_generation_unknown(self) -> None:
        request = AudioRequest.from_dict(valid_audio_request())
        attempt = AudioGenerationAttempt(
            1, "attempt-1", fingerprint_request(request.to_dict()), "small-sfx",
            AudioGenerationMode.TEXT_TO_AUDIO, 7, {}, AudioAttemptStatus.GENERATION_UNKNOWN, NOW, NOW,
        )
        with self.assertRaisesRegex(ValueError, "must not be resubmitted"):
            attempt.assert_can_generate()

    def test_completed_attempt_requires_bound_output(self) -> None:
        request = AudioRequest.from_dict(valid_audio_request())
        with self.assertRaisesRegex(ValueError, "output path"):
            AudioGenerationAttempt(
                1, "attempt-1", fingerprint_request(request.to_dict()), "small-sfx",
                AudioGenerationMode.TEXT_TO_AUDIO, 7, {}, AudioAttemptStatus.COMPLETED, NOW, NOW,
            )


if __name__ == "__main__":
    unittest.main()
