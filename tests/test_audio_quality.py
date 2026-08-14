from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from tests._bootstrap import ROOT  # noqa: F401
from tests.test_audio_contract import valid_audio_request
from tests.test_audio_ingest import write_pcm_wav

from game_visual_forge.contracts.audio import AudioProcessedArtifact, AudioProcessingResult, AudioRequest
from game_visual_forge.contracts.audio_provider import AudioCandidateRecord, AudioGenerationResult
from game_visual_forge.jobs.fingerprints import fingerprint_request
from game_visual_forge.quality.audio import assess_audio_outputs


def make_fixture(root: Path, *, clipped: bool = False):
    request = AudioRequest.from_dict(valid_audio_request(duration_seconds=1.0))
    wav = root / request.output_dir / "staging" / "candidate-01.wav"
    write_pcm_wav(wav, seconds=1.0, channels=2)
    if clipped:
        import wave
        with wave.open(str(wav), "wb") as handle:
            handle.setnchannels(2)
            handle.setsampwidth(2)
            handle.setframerate(44100)
            handle.writeframes((32767).to_bytes(2, "little", signed=True) * 2 * 44100)
    waveform = wav.with_name("candidate-01-waveform.png")
    spectrum = wav.with_name("candidate-01-spectrum.png")
    waveform.write_bytes(b"waveform")
    spectrum.write_bytes(b"spectrum")
    fp = fingerprint_request(request.to_dict())
    processing = AudioProcessingResult(1, fp, (AudioProcessedArtifact(1, "candidate-01", wav.relative_to(root).as_posix(), waveform.relative_to(root).as_posix(), spectrum.relative_to(root).as_posix(), fp),), "outputs/iron-sword-hit/staging")
    generation = AudioGenerationResult(1, fp, request.mode, (AudioCandidateRecord(1, "candidate-01", "candidate-01", 1, "raw/candidate-01.wav", "a" * 64),), ())
    return request, generation, processing


class AudioQualityTests(unittest.TestCase):
    def test_clipping_is_a_hard_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            request, generation, processing = make_fixture(Path(directory), clipped=True)
            report = assess_audio_outputs(Path(directory), request, None, generation, processing)
            self.assertEqual(report.status, "failed")
            self.assertTrue(any("clipping" in failure for failure in report.failures))

    def test_clean_audio_passes_and_records_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request, generation, processing = make_fixture(root)
            report = assess_audio_outputs(root, request, None, generation, processing)
            self.assertEqual(report.status, "passed")
            self.assertEqual(len(report.artifacts["candidate-01"]["wav_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
