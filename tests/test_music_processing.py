import hashlib
import math
import tempfile
import unittest
import wave
from array import array
from pathlib import Path
from tests._bootstrap import ROOT  # noqa: F401
from game_visual_forge.contracts.music import MusicProcessingOptions, MusicSourceRecord
from game_visual_forge.processing.music import ingest_music_source, process_music_candidate


def write_wav(path, rate=32000, channels=1, seconds=1.0, amp=8000):
    frames = int(rate * seconds)
    values = array("h")
    for i in range(frames):
        sample = int(amp * math.sin(2 * math.pi * 440 * i / rate))
        values.extend([sample] * channels)
    with wave.open(str(path), "wb") as out:
        out.setnchannels(channels); out.setsampwidth(2); out.setframerate(rate); out.writeframes(values.tobytes())


class MusicProcessingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "inputs" / "tone.wav"; self.source.parent.mkdir(); write_wav(self.source, seconds=2, channels=1)
        self.before = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.record = ingest_music_source(self.root, self.source, type("Attempt", (), {"provider": "comfyui-music3", "attempt_id": "a", "request_fingerprint": "x"})(), Path("unused"))

    def test_ingest_is_relative_and_processing_normalizes(self):
        self.assertEqual(self.record.path, "inputs/tone.wav")
        result = process_music_candidate(self.root, self.record, MusicProcessingOptions(), Path("unused"), Path("unused"))
        self.assertEqual(result.sample_rate, 44100); self.assertEqual(result.channels, 2)
        self.assertAlmostEqual(result.duration_seconds, 2.0, places=2)
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), self.before)
        with self.assertRaises(ValueError):
            self.record.__class__("../escape.wav", self.record.sha256, "wav", 32000, 1, 2, "local", "a", "c")

    def test_trim_does_not_pad_short_source(self):
        result = process_music_candidate(self.root, self.record, MusicProcessingOptions("trim", 0.25, 1.25), Path("unused"), Path("unused"))
        self.assertAlmostEqual(result.duration_seconds, 1.0, places=2)
        with self.assertRaises(ValueError):
            process_music_candidate(self.root, self.record, MusicProcessingOptions("trim", 0, 3), Path("unused"), Path("unused"))

    def test_invalid_paths_are_rejected(self):
        with self.assertRaises(ValueError):
            ingest_music_source(self.root, self.root.parent / "escape.wav", type("Attempt", (), {"provider": "x", "attempt_id": "a"})(), Path("unused"))


if __name__ == "__main__": unittest.main()
