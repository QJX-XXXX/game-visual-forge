import tempfile
import unittest
import hashlib
from pathlib import Path
from tests._bootstrap import ROOT  # noqa: F401
from tests.test_music_processing import write_wav
from tests.test_music_contract import music_request
from game_visual_forge.contracts.music import MusicProcessingResult, MusicSourceRecord
from game_visual_forge.quality.music import assess_music_outputs, record_music_review
from game_visual_forge.contracts.music_review import REQUIRED_MUSIC_CHECKS


class MusicReviewTests(unittest.TestCase):
    def test_exact_six_music_checks_are_distinct_from_sfx(self):
        self.assertEqual(len(REQUIRED_MUSIC_CHECKS), 6)
        self.assertNotIn("transient-and-impact-clarity", REQUIRED_MUSIC_CHECKS)
        with self.assertRaises(ValueError):
            record_music_review(music_request(), MusicProcessingResult("a" * 64, "x", "b" * 64, "c" * 64, 44100, 2, 1, 44100, 2), None, {"wrong": True}, "2026-10-10T00:00:00Z")

    def test_review_binds_quality_and_artifact_hashes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); path = root / "track.wav"; write_wav(path, rate=44100, channels=2, seconds=1)
            source = MusicSourceRecord("track.wav", hashlib.sha256(path.read_bytes()).hexdigest(), "wav", 44100, 2, 1, "local", "a", "c")
            processing = MusicProcessingResult(source.sha256, str(path), "b" * 64, "c" * 64, 44100, 2, 1, 44100, 2)
            quality = assess_music_outputs(music_request(usage="bgm-linear"), source, processing, repo_root=root)
            review = record_music_review(music_request(usage="bgm-linear"), processing, quality, {key: True for key in REQUIRED_MUSIC_CHECKS}, now="2026-10-10T00:00:00Z", repo_root=root)
            self.assertTrue(all(review.checks.values()))
            path.write_bytes(path.read_bytes() + b"x")
            with self.assertRaises(ValueError):
                review.assert_current(processing, quality, repo_root=root)
            path.write_bytes(path.read_bytes()[:-1])
            processing = MusicProcessingResult(source.sha256, str(path), "b" * 64, "c" * 64, 44100, 2, 1, 44100, 2, source_path="track.wav")
            quality = assess_music_outputs(music_request(usage="bgm-linear"), source, processing, repo_root=root)
            review = record_music_review(music_request(usage="bgm-linear"), processing, quality, {key: True for key in REQUIRED_MUSIC_CHECKS}, now="2026-10-10T00:00:00Z", repo_root=root)
            path.write_bytes(path.read_bytes() + b"raw-change")
            with self.assertRaises(ValueError):
                review.assert_current(processing, quality, repo_root=root)


if __name__ == "__main__": unittest.main()
