from __future__ import annotations

import tempfile
import unittest
import wave
from pathlib import Path

from tests._bootstrap import ROOT  # noqa: F401
from tests.test_audio_contract import valid_audio_request
from tests.test_audio_ingest import write_pcm_wav

from game_visual_forge.contracts.audio import AudioRequest
from game_visual_forge.contracts.audio_provider import AudioCandidateRecord, AudioGenerationResult
from game_visual_forge.jobs.fingerprints import fingerprint_request
from game_visual_forge.processing.audio import _limit_pcm16_peak, process_audio_candidates
from game_visual_forge.processing.audio_metrics import read_pcm16_metrics


FAKE_FFMPEG = ROOT / "tests" / "fixtures" / "fake_audio_ffmpeg.py"


def write_pcm_samples(path: Path, values: list[int], channels: int = 1, rate: int = 44100) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        import array
        samples = array.array("h", values)
        handle.writeframes(samples.tobytes())


class AudioProcessingTests(unittest.TestCase):
    def test_peak_ceiling_attenuates_hot_audio_without_changing_shape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hot.wav"
            write_pcm_samples(path, [30000, -30000] * 200, channels=2)
            before = read_pcm16_metrics(path)

            self.assertTrue(_limit_pcm16_peak(path))

            after = read_pcm16_metrics(path)
            target = round(32767 * (10 ** (-1.0 / 20.0)))
            self.assertLessEqual(abs(after.peak_sample - target), 1)
            self.assertEqual(after.frame_count, before.frame_count)
            self.assertEqual(after.sample_rate, before.sample_rate)
            self.assertEqual(after.channels, before.channels)

    def test_peak_ceiling_leaves_quiet_silence_and_clipping_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixtures = (
                ("quiet.wav", [1000, -1000, 0, 0]),
                ("silent.wav", [0, 0, 0, 0]),
                ("clipped.wav", [32767, -32767, 0, 0]),
            )
            for name, samples in fixtures:
                with self.subTest(name=name):
                    path = root / name
                    write_pcm_samples(path, samples, channels=2)
                    before = path.read_bytes()

                    self.assertFalse(_limit_pcm16_peak(path))
                    self.assertEqual(path.read_bytes(), before)

    def test_pcm_metrics_detect_peak_clipping_dc_and_silence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metric.wav"
            write_pcm_samples(path, [0, 0, 32767, 1000, 1000])
            metrics = read_pcm16_metrics(path)
            self.assertEqual(metrics.sample_rate, 44100)
            self.assertEqual(metrics.bit_depth, 16)
            self.assertEqual(metrics.clipped_sample_count, 1)
            self.assertGreater(metrics.dc_offset_abs, 0)
            self.assertGreater(metrics.silent_sample_ratio, 0)

    def test_process_writes_pcm_candidate_and_previews(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request = AudioRequest.from_dict(valid_audio_request(duration_seconds=1.0, unity_import_requested=False))
            raw = root / request.output_dir / "raw" / "candidate-01.wav"
            write_pcm_wav(raw, seconds=1.0, channels=2)
            digest = "a" * 64
            generation = AudioGenerationResult(1, fingerprint_request(request.to_dict()), request.mode, (AudioCandidateRecord(1, "candidate-01", "candidate-01", 1, "raw/candidate-01.wav", digest),), ())
            result = process_audio_candidates(root, request, generation, None, FAKE_FFMPEG, FAKE_FFMPEG)
            artifact = result.artifacts[0]
            self.assertTrue((root / artifact.wav_path).is_file())
            self.assertTrue((root / artifact.waveform_path).is_file())
            self.assertEqual(read_pcm16_metrics(root / artifact.wav_path).sample_rate, 44100)

    def test_process_does_not_boost_quiet_generated_one_shot_staging(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request = AudioRequest.from_dict(
                valid_audio_request(
                    duration_seconds=1.0,
                    spatial_mode="2d",
                    unity_import_requested=False,
                )
            )
            raw = root / request.output_dir / "raw" / "candidate-01.wav"
            write_pcm_samples(raw, [1000, -1000] * 44100, channels=2)
            raw_before = raw.read_bytes()
            generation = AudioGenerationResult(
                1,
                fingerprint_request(request.to_dict()),
                request.mode,
                (
                    AudioCandidateRecord(
                        1,
                        "candidate-01",
                        "candidate-01",
                        1,
                        "raw/candidate-01.wav",
                        "a" * 64,
                    ),
                ),
                (),
            )

            result = process_audio_candidates(root, request, generation, None, FAKE_FFMPEG, FAKE_FFMPEG)

            metrics = read_pcm16_metrics(root / result.artifacts[0].wav_path)
            self.assertEqual(raw.read_bytes(), raw_before)
            self.assertEqual(metrics.peak_sample, 1000)
            self.assertEqual(metrics.frame_count, 44100)
            self.assertEqual(metrics.channels, 2)

    def test_process_does_not_normalize_ui_staging(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request = AudioRequest.from_dict(
                valid_audio_request(
                    duration_seconds=1.0,
                    usage_profile="ui",
                    spatial_mode="2d",
                    unity_import_requested=False,
                )
            )
            raw = root / request.output_dir / "raw" / "candidate-01.wav"
            write_pcm_samples(raw, [1000, -1000] * 44100, channels=2)
            generation = AudioGenerationResult(
                1,
                fingerprint_request(request.to_dict()),
                request.mode,
                (
                    AudioCandidateRecord(
                        1,
                        "candidate-01",
                        "candidate-01",
                        1,
                        "raw/candidate-01.wav",
                        "a" * 64,
                    ),
                ),
                (),
            )

            result = process_audio_candidates(root, request, generation, None, FAKE_FFMPEG, FAKE_FFMPEG)

            self.assertEqual((root / result.artifacts[0].wav_path).read_bytes(), raw.read_bytes())


if __name__ == "__main__":
    unittest.main()
