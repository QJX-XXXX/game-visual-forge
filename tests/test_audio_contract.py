from __future__ import annotations

import unittest

from tests._bootstrap import ROOT  # noqa: F401

from game_visual_forge.contracts.audio import (
    AudioGenerationMode,
    AudioRequest,
    AudioSpatialMode,
    AudioUsageProfile,
)


def valid_audio_request(**overrides):
    value = {
        "schema_version": 1,
        "asset_id": "iron-sword-hit",
        "mode": "text-to-audio",
        "prompt": "A short iron sword impact against a steel shield",
        "output_dir": "outputs/iron-sword-hit",
        "duration_seconds": 2.0,
        "usage_profile": "one-shot",
        "spatial_mode": "3d",
        "loop": False,
        "candidate_count": 3,
        "join_guard_ms": 20,
        "loop_analysis_ms": 50,
        "loop_crossfade_ms": 20,
        "unity_import_requested": True,
        "unity_scene_placement_requested": False,
    }
    value.update(overrides)
    return value


class AudioContractTests(unittest.TestCase):
    def test_all_modes_round_trip_and_defaults(self) -> None:
        for mode in AudioGenerationMode:
            source = None if mode is AudioGenerationMode.TEXT_TO_AUDIO else "inputs/source.wav"
            values = valid_audio_request(
                mode=mode.value,
                source_path=source,
                candidate_count=None,
                edit_start_seconds=0.2 if mode is AudioGenerationMode.INPAINT else None,
                edit_end_seconds=0.6 if mode is AudioGenerationMode.INPAINT else None,
            )
            request = AudioRequest.from_dict(values)
            expected_count = 3 if mode in {AudioGenerationMode.TEXT_TO_AUDIO, AudioGenerationMode.REDRAW} else 1
            self.assertEqual(request.candidate_count, expected_count)
            self.assertEqual(AudioRequest.from_dict(request.to_dict()), request)

    def test_mode_defaults_and_source_requirements(self) -> None:
        request = AudioRequest.from_dict(valid_audio_request())
        self.assertEqual(request.candidate_count, 3)
        with self.assertRaisesRegex(ValueError, "source_path"):
            AudioRequest.from_dict(valid_audio_request(mode="inpaint", candidate_count=1))
        with self.assertRaisesRegex(ValueError, "edit"):
            AudioRequest.from_dict(
                valid_audio_request(
                    mode="inpaint", source_path="inputs/source.wav", candidate_count=1
                )
            )

    def test_redraw_and_continue_require_source(self) -> None:
        for mode in ("redraw", "continue"):
            with self.subTest(mode=mode):
                with self.assertRaisesRegex(ValueError, "source_path"):
                    AudioRequest.from_dict(valid_audio_request(mode=mode, candidate_count=1))

    def test_paths_and_numeric_limits_are_validated(self) -> None:
        with self.assertRaisesRegex(ValueError, "output_dir"):
            AudioRequest.from_dict(valid_audio_request(output_dir="../outside"))
        with self.assertRaisesRegex(ValueError, "duration"):
            AudioRequest.from_dict(valid_audio_request(duration_seconds=121))
        with self.assertRaisesRegex(ValueError, "candidate_count"):
            AudioRequest.from_dict(valid_audio_request(candidate_count=9))
        with self.assertRaisesRegex(ValueError, "distance"):
            AudioRequest.from_dict(valid_audio_request(max_distance=1, min_distance=2))

    def test_enum_values_are_stable(self) -> None:
        self.assertEqual(AudioGenerationMode.TEXT_TO_AUDIO.value, "text-to-audio")
        self.assertEqual(AudioUsageProfile.LOOPING_AMBIENCE.value, "looping-ambience")
        self.assertEqual(AudioSpatialMode.THREE_D.value, "3d")


if __name__ == "__main__":
    unittest.main()
