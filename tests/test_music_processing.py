import hashlib
import math
import shutil
import subprocess
import tempfile
import unittest
import wave
from array import array
from pathlib import Path
from tests._bootstrap import ROOT
from tests.test_music_contract import music_request
from tests.test_music_provider_orchestration import attempt
from game_visual_forge.cli.music import run_music_ingest, run_music_process
from game_visual_forge.contracts.music import MusicProcessingOptions, MusicSourceRecord
from game_visual_forge.contracts.serialization import dump_json
from game_visual_forge.processing.music import ingest_music_source, process_music_candidate
from game_visual_forge.quality.music import assess_music_outputs


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

    def test_same_basename_keeps_each_candidate_and_detects_overwrite(self):
        different = self.root / "other" / "tone.wav"
        different.parent.mkdir()
        write_wav(different, seconds=1, amp=5000)
        other = ingest_music_source(self.root, different, attempt())
        first = process_music_candidate(self.root, self.record, MusicProcessingOptions())
        second = process_music_candidate(self.root, other, MusicProcessingOptions())
        self.assertNotEqual(first.processed_path, second.processed_path)
        request = music_request(usage="bgm-linear")
        self.assertEqual(assess_music_outputs(request, self.record, first, repo_root=self.root).status, "passed")
        shutil.copyfile(self.root / second.processed_path, self.root / first.processed_path)
        report = assess_music_outputs(request, self.record, first, repo_root=self.root)
        self.assertEqual(report.status, "failed")
        self.assertIn("processed-hash-mismatch", report.failures)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "requires installed FFmpeg and FFprobe")
    def test_mp3_ingest_and_process_use_original_hash_and_deliver_pcm_wav(self):
        ffmpeg, ffprobe = Path(shutil.which("ffmpeg")), Path(shutil.which("ffprobe"))
        mp3 = self.source.with_suffix(".mp3")
        subprocess.run([str(ffmpeg), "-v", "error", "-i", str(self.source), "-c:a", "libmp3lame", str(mp3)], check=True)
        attempt_path = self.root / "attempt.json"
        dump_json(attempt_path, attempt().to_dict())
        source_path = self.root / "source.json"
        ingested = run_music_ingest(None, mp3, self.root, attempt_path, source_path, ffprobe)
        self.assertEqual(ingested["codec_name"], "mp3")
        self.assertEqual(ingested["path"], "inputs/tone.mp3")
        result = run_music_process(source_path, None, self.root, self.root / "processed.json", ffmpeg)
        with wave.open(str(self.root / result["processed_path"]), "rb") as handle:
            self.assertEqual((handle.getframerate(), handle.getnchannels(), handle.getsampwidth()), (44100, 2, 2))
            self.assertAlmostEqual(handle.getnframes() / 44100, 2, places=2)
        self.assertEqual(result["source_sha256"], hashlib.sha256(mp3.read_bytes()).hexdigest())


if __name__ == "__main__": unittest.main()
