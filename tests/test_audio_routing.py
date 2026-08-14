from __future__ import annotations

import types
import unittest

from tests._bootstrap import ROOT  # noqa: F401
from tests.test_audio_contract import valid_audio_request

from game_visual_forge.contracts.audio import AudioRequest
from game_visual_forge.routing.audio import route_audio


class AudioRoutingTests(unittest.TestCase):
    def test_missing_preflight_requires_user_action_and_is_not_paid(self) -> None:
        request = AudioRequest.from_dict(valid_audio_request())
        result = route_audio(request, None)
        self.assertTrue(result.requires_user_action)
        self.assertFalse(result.requires_paid_confirmation)
        self.assertEqual(result.selected_provider, "stable-audio-local")

    def test_local_model_preflight_unlocks_generation(self) -> None:
        request = AudioRequest.from_dict(valid_audio_request())
        preflight = types.SimpleNamespace(available=True, model_local=True)
        result = route_audio(request, preflight)
        self.assertFalse(result.requires_user_action)
        self.assertFalse(result.requires_paid_confirmation)
        self.assertEqual(result.reason, "local-small-sfx-ready")

    def test_missing_local_model_requires_user_action(self) -> None:
        request = AudioRequest.from_dict(valid_audio_request())
        preflight = types.SimpleNamespace(available=True, model_local=False)
        result = route_audio(request, preflight)
        self.assertTrue(result.requires_user_action)
        self.assertEqual(result.reason, "local-model-required")


if __name__ == "__main__":
    unittest.main()
