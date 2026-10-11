import tempfile
import unittest
import wave
import hashlib
from pathlib import Path
from tests._bootstrap import ROOT  # noqa: F401
from tests.test_music_processing import write_wav
from tests.test_music_contract import music_request
from game_visual_forge.contracts.music import MusicProcessingResult, MusicSourceRecord
from game_visual_forge.quality.music import assess_music_outputs


class MusicQualityTests(unittest.TestCase):
    def test_music_quality_does_not_use_sfx_dense_noise_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); path = root / "track.wav"; write_wav(path, rate=44100, channels=2, seconds=1, amp=28000)
            source = MusicSourceRecord("track.wav", hashlib.sha256(path.read_bytes()).hexdigest(), "wav", 44100, 2, 1, "local", "a", "c")
            processing = MusicProcessingResult(source.sha256, str(path), "b" * 64, "c" * 64, 44100, 2, 1, 44100, 2)
            report = assess_music_outputs(music_request(usage="bgm-linear"), source, processing, repo_root=root)
            self.assertEqual(report.status, "passed")
            self.assertNotIn("dense-noise", report.failures)

    def test_loop_requires_evidence_and_clipping_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); path = root / "track.wav"
            with wave.open(str(path), "wb") as handle:
                handle.setnchannels(2); handle.setsampwidth(2); handle.setframerate(44100)
                handle.writeframes((32767).to_bytes(2, "little", signed=True) * 2 * 44100)
            source = MusicSourceRecord("track.wav", hashlib.sha256(path.read_bytes()).hexdigest(), "wav", 44100, 2, 1, "local", "a", "c")
            processing = MusicProcessingResult(source.sha256, str(path), "b" * 64, "c" * 64, 44100, 2, 1, 44100, 2)
            report = assess_music_outputs(music_request(), source, processing, repo_root=root)
            self.assertEqual(report.status, "failed")
            self.assertIn("missing-loop-evidence", report.failures)
            self.assertIn("clipping", report.failures)


if __name__ == "__main__": unittest.main()
