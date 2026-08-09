from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests._bootstrap import ROOT

from game_visual_forge.processing.video_frames import extract_highest_density, sample_timestamps
from game_visual_forge.processing.video_probe import discover_toolchain, ingest_video


def optional_toolchain():
    try:
        return discover_toolchain()
    except FileNotFoundError:
        return None


@unittest.skipUnless(optional_toolchain() is not None, "FFmpeg/FFprobe not installed")
class RealFfmpegIntegrationTests(unittest.TestCase):
    def test_synthetic_video_probe_and_extract_round_trip(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            source = root / "synthetic.mp4"
            tools = optional_toolchain()
            assert tools is not None
            command = [str(tools.ffmpeg), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=64x64:rate=8", "-t", "1", "-pix_fmt", "yuv420p", str(source)]
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", shell=False, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            record = ingest_video(root, source, "a" * 64, ffprobe=tools.ffprobe)
            timestamps = sample_timestamps(0.0, min(0.9, record.duration_seconds), 8, loop=True)
            frames = extract_highest_density(root, record, timestamps, tools.ffmpeg, output_dir="staging/raw-frames")
            self.assertEqual(len(frames), 8)
            self.assertTrue(all((root / frame.raw_path).stat().st_size > 0 for frame in frames))


if __name__ == "__main__":
    unittest.main()
