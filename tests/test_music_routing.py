import unittest
from dataclasses import replace
from tests._bootstrap import ROOT  # noqa: F401
from tests.test_music_contract import music_request
from game_visual_forge.contracts.music_provider import MusicProvider, default_music_capabilities
from game_visual_forge.routing.music import route_music


class MusicRoutingTests(unittest.TestCase):
    def test_local_default_never_falls_back(self):
        caps = default_music_capabilities(local_ready=False)
        route = route_music(music_request(), caps)
        self.assertEqual(route.selected_provider, MusicProvider.COMFYUI_MUSIC3)
        self.assertEqual(route.status, "needs_user_action")
        self.assertFalse(route.requires_paid_confirmation)
        self.assertEqual(route_music(music_request(), default_music_capabilities(local_ready=True)).status, "ready")

    def test_suno_unknown_and_cloud_confirmation(self):
        caps = default_music_capabilities()
        suno = route_music(music_request(), caps, MusicProvider.SUNO_API)
        self.assertEqual(suno.status, "needs_user_action")
        self.assertIn("official", suno.reason)
        stable = caps[MusicProvider.STABLE_AUDIO_API]
        caps[stable.provider] = replace(stable, auth_verified=True)
        route = route_music(music_request(), caps, stable.provider)
        self.assertEqual(route.status, "ready")
        self.assertTrue(route.requires_paid_confirmation)

    def test_provider_bounds_and_vocals(self):
        caps = default_music_capabilities(local_ready=True)
        self.assertEqual(route_music(music_request(target_duration_seconds=370), caps).status, "unsupported_requirement")
        stable = caps[MusicProvider.STABLE_AUDIO_API]
        caps[stable.provider] = replace(stable, auth_verified=True)
        request = music_request(vocal_policy="vocals-required", lyrics="Hello")
        self.assertEqual(route_music(request, caps, stable.provider).status, "unsupported_requirement")
        self.assertEqual(route_music(music_request(target_duration_seconds=380), caps, stable.provider).status, "ready")


if __name__ == "__main__":
    unittest.main()
