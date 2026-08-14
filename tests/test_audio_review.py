from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests._bootstrap import ROOT  # noqa: F401
from tests.test_audio_contract import valid_audio_request
from tests.test_audio_quality import make_fixture

from game_visual_forge.contracts.audio_review import AudioReview, REQUIRED_AUDIO_CHECKS
from game_visual_forge.quality.audio import assess_audio_outputs, record_audio_review


CHECKS = {item: True for item in REQUIRED_AUDIO_CHECKS}


class AudioReviewTests(unittest.TestCase):
    def test_review_requires_exact_six_checks(self) -> None:
        with self.assertRaisesRegex(ValueError, "exactly"):
            AudioReview.create(request_fingerprint="a" * 64, selected_candidate_id="candidate-01", quality_report_sha256="b" * 64, artifact_sha256={"wav": "c" * 64, "waveform": "d" * 64, "spectrum": "e" * 64}, checks={"prompt-and-action-match": True}, reviewed_at="2026-08-14T00:00:00Z")

    def test_false_check_is_recorded_but_blocks_later_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request, generation, processing = make_fixture(root)
            report = assess_audio_outputs(root, request, None, generation, processing)
            report_path = root / "quality-report.json"
            report_path.write_text("{}", encoding="utf-8")
            artifact = processing.artifacts[0]
            checks = dict(CHECKS)
            checks["noise-and-generation-artifacts"] = False
            review = record_audio_review(root, request, generation, processing, report_path, "candidate-01", {"wav": root / artifact.wav_path, "waveform": root / artifact.waveform_path, "spectrum": root / artifact.spectrum_path}, checks, "2026-08-14T00:00:00Z")
            self.assertFalse(review.checks["noise-and-generation-artifacts"])


if __name__ == "__main__":
    unittest.main()
