import math
import tempfile
import unittest
import wave
from array import array
from pathlib import Path
from tests._bootstrap import ROOT  # noqa: F401
from tests.test_music_processing import write_wav
from game_visual_forge.processing.music import build_music_loop_evidence


class MusicLoopTests(unittest.TestCase):
    def test_loop_evidence_has_boundary_and_three_round_audio(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "tone.wav"; write_wav(source, rate=44100, channels=2, seconds=2)
            evidence = build_music_loop_evidence(source, start_seconds=0.25, end_seconds=1.25, crossfade_ms=10, ffmpeg=Path("unused"))
            self.assertEqual(evidence.effective_frame_count, 44100 - 441)
            self.assertTrue(Path(evidence.three_round_path).exists())
            self.assertTrue(Path(evidence.boundary_preview_path).exists())
            with wave.open(evidence.three_round_path, "rb") as handle:
                self.assertEqual(handle.getnframes(), 3 * 44100 - 2 * 441)

    def test_loop_range_and_crossfade_bounds_are_hard_failures(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "tone.wav"; write_wav(source, seconds=1)
            with self.assertRaises(ValueError):
                build_music_loop_evidence(source, start_seconds=-1, end_seconds=0.5, crossfade_ms=0, ffmpeg=Path("unused"))
            with self.assertRaises(ValueError):
                build_music_loop_evidence(source, start_seconds=0, end_seconds=0.01, crossfade_ms=20, ffmpeg=Path("unused"))


if __name__ == "__main__": unittest.main()
