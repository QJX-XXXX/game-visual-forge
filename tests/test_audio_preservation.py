from __future__ import annotations

import tempfile
import unittest
import wave
import hashlib
from pathlib import Path

from tests._bootstrap import ROOT  # noqa: F401
from tests.test_audio_ingest import write_pcm_wav
from tests.test_audio_contract import valid_audio_request

from game_visual_forge.processing.audio_metrics import compare_protected_samples
from game_visual_forge.contracts.audio import AudioRequest, AudioSourceRecord
from game_visual_forge.contracts.audio_provider import AudioCandidateRecord, AudioGenerationResult
from game_visual_forge.jobs.fingerprints import fingerprint_request
from game_visual_forge.processing.audio import process_audio_candidates

FAKE_FFMPEG = ROOT / "tests" / "fixtures" / "fake_audio_ffmpeg.py"


class AudioPreservationTests(unittest.TestCase):
    def test_inpaint_preserves_source_outside_mask_and_guards(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "source.wav"
            generated_path = root / "outputs" / "hit" / "raw" / "candidate-01.wav"
            write_pcm_wav(source_path, seconds=1.0, channels=1)
            generated_path.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(generated_path), "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(2)
                handle.setframerate(44100)
                handle.writeframes(b"\x20\x00" * 44100)
            request = AudioRequest.from_dict(valid_audio_request(mode="inpaint", source_path="source.wav", output_dir="outputs/hit", candidate_count=1, edit_start_seconds=0.4, edit_end_seconds=0.6))
            fingerprint = fingerprint_request(request.to_dict())
            source = AudioSourceRecord(1, "source.wav", hashlib.sha256(source_path.read_bytes()).hexdigest(), "pcm_s16le", 44100, 1, "mono", "s16", 1.0, fingerprint)
            generation = AudioGenerationResult(1, fingerprint, request.mode, (AudioCandidateRecord(1, "candidate-01", "candidate-01", 1, "raw/candidate-01.wav", "a" * 64),), ())
            result = process_audio_candidates(root, request, generation, source, FAKE_FFMPEG, FAKE_FFMPEG)
            self.assertTrue(compare_protected_samples(source_path, root / result.artifacts[0].wav_path, ((0, round(0.38 * 44100)), (round(0.62 * 44100), 44100))))

    def test_continue_preserves_source_prefix_before_join_guard(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "source.wav"
            generated_path = root / "outputs" / "ambience" / "raw" / "candidate-01.wav"
            write_pcm_wav(source_path, seconds=1.0, channels=1)
            generated_path.parent.mkdir(parents=True, exist_ok=True)
            write_pcm_wav(generated_path, seconds=2.0, channels=1)
            request = AudioRequest.from_dict(valid_audio_request(mode="continue", source_path="source.wav", output_dir="outputs/ambience", duration_seconds=2.0, candidate_count=1))
            fingerprint = fingerprint_request(request.to_dict())
            source = AudioSourceRecord(1, "source.wav", hashlib.sha256(source_path.read_bytes()).hexdigest(), "pcm_s16le", 44100, 1, "mono", "s16", 1.0, fingerprint)
            generation = AudioGenerationResult(1, fingerprint, request.mode, (AudioCandidateRecord(1, "candidate-01", "candidate-01", 1, "raw/candidate-01.wav", "a" * 64),), ())
            result = process_audio_candidates(root, request, generation, source, FAKE_FFMPEG, FAKE_FFMPEG)
            self.assertTrue(compare_protected_samples(source_path, root / result.artifacts[0].wav_path, ((0, round(0.98 * 44100)),)))

    def test_protected_sample_ranges_detect_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.wav"
            actual = root / "actual.wav"
            write_pcm_wav(source, seconds=1.0, channels=1)
            write_pcm_wav(actual, seconds=1.0, channels=1)
            self.assertTrue(compare_protected_samples(source, actual, ((0, round(0.4 * 44100)), (round(0.6 * 44100), 44100))))

    def test_protected_sample_ranges_reject_changed_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.wav"
            actual = root / "actual.wav"
            write_pcm_wav(source, seconds=1.0, channels=1)
            with wave.open(str(actual), "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(2)
                handle.setframerate(44100)
                handle.writeframes(b"\x01\x00" * 44100)
            self.assertFalse(compare_protected_samples(source, actual, ((0, 100),)))


if __name__ == "__main__":
    unittest.main()
