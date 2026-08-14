from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests._bootstrap import ROOT  # noqa: F401
from tests.test_audio_quality import make_fixture
from tests.test_audio_review import CHECKS

from game_visual_forge.contracts.audio_review import AudioReview
from game_visual_forge.quality.audio import assess_audio_outputs, build_audio_manifests, publish_audio_outputs, record_audio_review, validate_reviewed_audio_outputs


class AudioPublicationTests(unittest.TestCase):
    def test_approved_bundle_publishes_wav_and_manifests_without_placement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request, generation, processing = make_fixture(root)
            report = assess_audio_outputs(root, request, None, generation, processing)
            report_path = root / "quality-report.json"
            report_path.write_text(json.dumps(report.to_dict()), encoding="utf-8")
            artifact = processing.artifacts[0]
            review = record_audio_review(root, request, generation, processing, report_path, "candidate-01", {"wav": root / artifact.wav_path, "waveform": root / artifact.waveform_path, "spectrum": root / artifact.spectrum_path}, CHECKS, "2026-08-14T00:00:00Z")
            validated = validate_reviewed_audio_outputs(root, request, generation, processing, report, review)
            self.assertEqual(validated.status, "passed")
            manifests = build_audio_manifests(root, request, generation, processing, validated, review)
            final = root / "final"
            publish_audio_outputs(root / processing.staging_dir, final, [root / artifact.wav_path], manifests)
            self.assertTrue((final / "audio-manifest.json").is_file())
            self.assertTrue((final / "unity-audio-manifest.json").is_file())
            self.assertFalse((final / "audio-source-placement.json").exists())


if __name__ == "__main__":
    unittest.main()
