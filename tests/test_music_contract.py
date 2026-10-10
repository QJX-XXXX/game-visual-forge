import unittest
from dataclasses import replace

from tests._bootstrap import ROOT  # noqa: F401
from tests.test_audio_contract import valid_audio_request
from game_visual_forge.contracts.audio import AudioRequest
from game_visual_forge.contracts.music import MusicRequest, MusicProcessingOptions, build_music_prompt_package, generation_fingerprint
from game_visual_forge.contracts.music_provider import MusicProvider, default_music_capabilities


def music_request(**changes):
    values = dict(schema_version=1, asset_id="puzzle-bgm", brief="Gentle marimba and felt piano for a puzzle game", usage="bgm-loop", target_duration_seconds=180, output_dir="outputs/puzzle-bgm")
    values.update(changes)
    return MusicRequest.from_dict(values)


class MusicContractTests(unittest.TestCase):
    def test_long_music_round_trip_and_instrumental_default(self):
        request = music_request()
        self.assertEqual(MusicRequest.from_dict(request.to_dict()), request)
        self.assertEqual(request.vocal_policy.value, "instrumental")
        self.assertEqual(request.candidate_count, 1)
        with self.assertRaises(ValueError):
            AudioRequest.from_dict(valid_audio_request(duration_seconds=121))

    def test_strict_instrumental_and_lyrics(self):
        for changes in [dict(usage="standalone-instrumental", lyrics="la la"), dict(usage="standalone-instrumental", vocal_policy="vocals-allowed"), dict(vocal_policy="instrumental", lyrics="Words")]:
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "instrumental"):
                music_request(**changes)
        self.assertEqual(music_request(vocal_policy="vocals-required", lyrics="[Verse]\nHello").lyrics, "[Verse]\nHello")

    def test_duration_counts_paths_and_types(self):
        for duration in [0, -1, float("inf"), float("nan"), 381, True]:
            with self.subTest(duration=duration), self.assertRaises((ValueError, TypeError)):
                music_request(target_duration_seconds=duration)
        for count in [0, 9, True, 1.5]:
            with self.subTest(count=count), self.assertRaises((ValueError, TypeError)):
                music_request(candidate_count=count)
        for path in ["../escape", "G:/absolute", "outputs/../../escape"]:
            with self.assertRaises(ValueError):
                music_request(output_dir=path)

    def test_prompt_preserves_constraints_and_vocal_policy(self):
        request = music_request(instruments=["piano"], exclusions=["drums"], tempo_bpm=90)
        package = build_music_prompt_package(request, MusicProvider.COMFYUI_MUSIC3, "A gentle track")
        self.assertIn("no vocals", package.caption)
        self.assertIn("piano", package.caption)
        self.assertIn("drums", package.caption)
        self.assertEqual(package.lyrics, "[instrumental]")
        self.assertEqual(package.original_brief, request.brief)

    def test_processing_changes_do_not_change_generation_fingerprint(self):
        request = music_request()
        cap = default_music_capabilities(local_ready=True)[MusicProvider.COMFYUI_MUSIC3]
        prompt = build_music_prompt_package(request, cap.provider, request.brief)
        first = generation_fingerprint(request, prompt, cap, {"seed": 42})
        self.assertEqual(first, generation_fingerprint(replace(request, asset_id="other", output_dir="outputs/other"), prompt, cap, {"seed": 42}))
        self.assertNotEqual(first, generation_fingerprint(request, prompt, cap, {"seed": 43}))
        MusicProcessingOptions.from_dict({"loop_start_seconds": 10, "loop_end_seconds": 50})


if __name__ == "__main__":
    unittest.main()
