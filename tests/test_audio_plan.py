from __future__ import annotations

import unittest

from tests._bootstrap import ROOT  # noqa: F401
from tests.test_audio_contract import valid_audio_request

from game_visual_forge.contracts.audio import (
    AudioIntakeStatus,
    assess_audio_intake,
    audio_confirmation_sha256,
)


class AudioPlanTests(unittest.TestCase):
    def test_intake_groups_missing_fields_once_and_writes_nothing(self) -> None:
        result = assess_audio_intake({"schema_version": 1, "asset_id": "sword-hit"})
        self.assertEqual(result.status, AudioIntakeStatus.NEEDS_USER_INPUT)
        self.assertEqual(
            [group.value for group in result.missing_groups],
            ["sound", "mode-and-source", "delivery"],
        )

    def test_complete_unconfirmed_intake_returns_one_confirmation_summary(self) -> None:
        result = assess_audio_intake(valid_audio_request())
        self.assertEqual(result.status, AudioIntakeStatus.NEEDS_USER_CONFIRMATION)
        self.assertIn("iron-sword-hit", result.confirmation_summary)
        self.assertEqual(len(result.confirmation_sha256), 64)

    def test_exact_confirmation_hash_unlocks_plan(self) -> None:
        request = assess_audio_intake(valid_audio_request()).request
        digest = audio_confirmation_sha256(request)
        result = assess_audio_intake(request.to_dict(), confirmed_sha256=digest)
        self.assertEqual(result.status, AudioIntakeStatus.PLANNED)

    def test_changed_request_invalidates_confirmation_hash(self) -> None:
        first = assess_audio_intake(valid_audio_request())
        payload = valid_audio_request(prompt="A different sound")
        result = assess_audio_intake(payload, confirmed_sha256=first.confirmation_sha256)
        self.assertEqual(result.status, AudioIntakeStatus.NEEDS_USER_CONFIRMATION)


if __name__ == "__main__":
    unittest.main()
