from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests._bootstrap import ROOT

from game_visual_forge.contracts.video import VideoSourceRecord
from game_visual_forge.processing.video_frames import (
    build_sampling_plan,
    derive_density_indices,
    extract_highest_density,
    sample_timestamps,
)


class VideoSamplingTests(unittest.TestCase):
    def test_loop_excludes_duplicate_endpoint(self) -> None:
        self.assertEqual(sample_timestamps(1.0, 2.0, 4, loop=True), (1.0, 1.25, 1.5, 1.75))

    def test_non_loop_includes_both_endpoints(self) -> None:
        self.assertEqual(sample_timestamps(1.0, 2.0, 3, loop=False), (1.0, 1.5, 2.0))

    def test_one_frame_uses_start(self) -> None:
        self.assertEqual(sample_timestamps(1.0, 2.0, 1, loop=False), (1.0,))

    def test_lower_densities_are_indices_into_highest_timeline(self) -> None:
        plan = build_sampling_plan(0.0, 2.0, (8, 16, 24, 48), loop=True)
        self.assertEqual(plan.extract_count, 48)
        self.assertEqual(len(plan.indices_by_count[8]), 8)
        self.assertTrue(set(plan.indices_by_count[24]).issubset(range(48)))

    def test_density_indices_are_ordered_and_unique(self) -> None:
        indices = derive_density_indices(48, 8)
        self.assertEqual(len(indices), 8)
        self.assertEqual(tuple(sorted(set(indices))), indices)
        self.assertEqual(indices[0], 0)

    def test_fake_ffmpeg_extracts_highest_density_once_per_timestamp(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            source = root / "source.mp4"
            source.write_bytes(b"source")
            record = VideoSourceRecord(1, "source.mp4", "a" * 64, "mp4", "h264", 64, 64, 0, 1.0, "24/1", "24/1", False, 24, False, "b" * 64)
            frames = extract_highest_density(root, record, (0.0, 0.25, 0.5, 0.75), ROOT / "tests" / "fixtures" / "fake_ffmpeg.py")
            self.assertEqual(len(frames), 4)
            self.assertTrue(all((root / frame.raw_path).is_file() for frame in frames))


if __name__ == "__main__":
    unittest.main()
