from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests._bootstrap import ROOT

from game_visual_forge.contracts.video_review import VideoMotionReview
from game_visual_forge.processing.video_probe import sha256_file
from game_visual_forge.processing.video_review import (
    calculate_temporal_metrics,
    create_anchor_diagnostic,
    create_contact_sheet,
    create_motion_difference,
    record_video_motion_review,
    validate_video_motion_review,
)


def frames():
    from PIL import Image
    result = []
    for index in range(4):
        image = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        for x in range(4 + index * 2, 12 + index * 2):
            for y in range(8, 24):
                image.putpixel((x, y), (255, 255, 255, 255))
        result.append(image)
    return tuple(result)


class VideoReviewTests(unittest.TestCase):
    def test_review_images_and_metrics_are_created(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            output = root / "preview"
            contact = create_contact_sheet(frames(), (0.0, 0.25, 0.5, 0.75), output / "contact-sheet.png")
            motion = create_motion_difference(frames(), output / "motion-difference.png")
            anchor = create_anchor_diagnostic(frames(), output / "anchor-diagnostic.png")
            self.assertTrue(contact.is_file() and motion.is_file() and anchor.is_file())
            metrics = calculate_temporal_metrics(frames())
            self.assertGreater(metrics.motion_coverage, 0)
            self.assertEqual(metrics.frame_count, 4)

    def test_static_hold_is_attention_not_failure(self) -> None:
        from PIL import Image
        repeated = (Image.new("RGBA", (8, 8), (255, 255, 255, 255)),) * 4
        metrics = calculate_temporal_metrics(repeated)
        self.assertGreater(metrics.exact_duplicate_rate, 0.5)
        self.assertIn("static-interval", metrics.attention_reasons)

    def test_review_becomes_stale_when_artifact_changes(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            quality = root / "quality.json"
            quality.write_text("{\"schema_version\":1}", encoding="utf-8")
            artifact = root / "preview.gif"
            artifact.write_bytes(b"gif")
            review = record_video_motion_review(root, "a" * 64, "b" * 64, quality, {"preview.gif": artifact}, {"action": True}, True, "2026-08-09T00:00:00Z")
            artifact.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "hash"):
                validate_video_motion_review(root, review, quality, {"preview.gif": artifact})


if __name__ == "__main__":
    unittest.main()
