import unittest
from tests._bootstrap import ROOT  # noqa: F401
from tests.test_music_contract import music_request
from game_visual_forge.contracts.music_provider import MusicProvider, default_music_capabilities
from game_visual_forge.routing.music import route_music


class MusicSkillBehaviorTests(unittest.TestCase):
    def test_default_local_and_explicit_suno_gate(self):
        caps = default_music_capabilities(local_ready=False)
        self.assertEqual(route_music(music_request(), caps).selected_provider, MusicProvider.COMFYUI_MUSIC3)
        self.assertEqual(route_music(music_request(), caps, MusicProvider.SUNO_API).status, "needs_user_action")

    def test_pure_music_and_explicit_vocal_request_are_distinct(self):
        pure = music_request(usage="standalone-instrumental")
        self.assertEqual(pure.vocal_policy.value, "instrumental")
        voiced = music_request(vocal_policy="vocals-required", lyrics="[Verse] hello")
        self.assertEqual(voiced.vocal_policy.value, "vocals-required")


if __name__ == "__main__": unittest.main()
