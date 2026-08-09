from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests._bootstrap import ROOT

from game_visual_forge.processing.video_probe import (
    discover_toolchain,
    ingest_video,
    parse_ffprobe_json,
    validate_trim,
)


def ffprobe_payload(*, rotation: int = 90, avg: str = "30/1", real: str = "30000/1001") -> dict:
    return {
        "streams": [
            {
                "index": 0,
                "codec_type": "video",
                "codec_name": "h264",
                "width": 720,
                "height": 1280,
                "duration": "2.5",
                "avg_frame_rate": avg,
                "r_frame_rate": real,
                "nb_frames": "75",
                "tags": {"rotate": str(rotation)},
            },
            {"index": 1, "codec_type": "audio", "codec_name": "aac"},
        ],
        "format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "duration": "2.5"},
    }


class VideoProbeTests(unittest.TestCase):
    def test_probe_normalizes_rotation_and_detects_vfr(self) -> None:
        metadata = parse_ffprobe_json(ffprobe_payload())
        self.assertEqual((metadata.width, metadata.height), (1280, 720))
        self.assertEqual(metadata.display_rotation, 90)
        self.assertTrue(metadata.variable_frame_rate)
        self.assertTrue(metadata.audio_present)

    def test_invalid_media_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "video stream"):
            parse_ffprobe_json({"streams": [], "format": {"duration": "1"}})
        with self.assertRaisesRegex(ValueError, "dimensions"):
            payload = ffprobe_payload()
            payload["streams"][0]["width"] = 0
            parse_ffprobe_json(payload)

    def test_trim_interval_is_validated(self) -> None:
        self.assertEqual(validate_trim(0.5, 2.0, 2.5), (0.5, 2.0))
        with self.assertRaisesRegex(ValueError, "clip_start_seconds"):
            validate_trim(-0.1, 1.0, 2.5)
        with self.assertRaisesRegex(ValueError, "clip_end_seconds"):
            validate_trim(0.5, 3.0, 2.5)

    def test_tool_discovery_prefers_explicit_then_environment(self) -> None:
        with patch.dict(os.environ, {"GAME_VISUAL_FORGE_FFMPEG": "env-ffmpeg", "GAME_VISUAL_FORGE_FFPROBE": "env-ffprobe"}, clear=False):
            toolchain = discover_toolchain(explicit_ffmpeg="explicit-ffmpeg", which=lambda name: f"path-{name}")
        self.assertEqual(toolchain.ffmpeg, Path("explicit-ffmpeg"))
        self.assertEqual(toolchain.ffprobe, Path("env-ffprobe"))

    def test_ingest_does_not_reencode_source(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            source = root / "walk.mp4"
            source.write_bytes(b"source-video")
            payload = root / "ffprobe.json"
            payload.write_text(json.dumps(ffprobe_payload(rotation=0)), encoding="utf-8")
            fake = ROOT / "tests" / "fixtures" / "fake_ffprobe.py"
            with patch.dict(os.environ, {"GAME_VISUAL_FORGE_FAKE_FFPROBE_JSON": str(payload)}, clear=False):
                record = ingest_video(root, source, "a" * 64, ffprobe= fake)
            self.assertEqual(record.path, "walk.mp4")
            self.assertEqual(source.read_bytes(), b"source-video")
            self.assertEqual(record.audio_present, True)


if __name__ == "__main__":
    unittest.main()
