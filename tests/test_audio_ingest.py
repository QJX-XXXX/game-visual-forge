from __future__ import annotations

import hashlib
import tempfile
import unittest
import wave
from pathlib import Path

from tests._bootstrap import ROOT  # noqa: F401
from tests.test_audio_contract import valid_audio_request

from game_visual_forge.contracts.audio import AudioRequest
from game_visual_forge.jobs.fingerprints import fingerprint_request
from game_visual_forge.processing.audio_probe import ingest_audio


FAKE_FFPROBE = ROOT / "tests" / "fixtures" / "fake_audio_ffprobe.py"


def write_pcm_wav(path: Path, seconds: float = 1.0, channels: int = 1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(44100)
        handle.writeframes(b"\x00\x00" * int(44100 * seconds) * channels)


class AudioIngestTests(unittest.TestCase):
    def test_ingest_binds_unicode_path_and_sha256(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "inputs" / "剑击.wav"
            write_pcm_wav(source)
            request = AudioRequest.from_dict(valid_audio_request(source_path="inputs/剑击.wav", mode="redraw", candidate_count=3))
            fingerprint = fingerprint_request(request.to_dict())
            record = ingest_audio(root, source, request, fingerprint, ffprobe=FAKE_FFPROBE)
            self.assertEqual(record.path, "inputs/剑击.wav")
            self.assertEqual(record.sha256, hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertEqual(record.duration_seconds, 1.0)

    def test_inpaint_and_continue_validate_source_duration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.wav"
            write_pcm_wav(source)
            inpaint = AudioRequest.from_dict(valid_audio_request(mode="inpaint", source_path="source.wav", candidate_count=1, edit_start_seconds=0.4, edit_end_seconds=1.2))
            with self.assertRaisesRegex(ValueError, "inside source duration"):
                ingest_audio(root, source, inpaint, fingerprint_request(inpaint.to_dict()), ffprobe=FAKE_FFPROBE)
            continuation = AudioRequest.from_dict(valid_audio_request(mode="continue", source_path="source.wav", candidate_count=1, duration_seconds=1.0))
            with self.assertRaisesRegex(ValueError, "greater than source"):
                ingest_audio(root, source, continuation, fingerprint_request(continuation.to_dict()), ffprobe=FAKE_FFPROBE)


if __name__ == "__main__":
    unittest.main()
