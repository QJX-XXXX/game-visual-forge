from __future__ import annotations

import unittest

from tests._bootstrap import ROOT  # noqa: F401

from game_visual_forge.processing.audio_probe import parse_audio_ffprobe_json


class AudioProbeTests(unittest.TestCase):
    def test_probe_requires_one_audio_stream(self) -> None:
        with self.assertRaisesRegex(ValueError, "audio stream"):
            parse_audio_ffprobe_json({"streams": [], "format": {"duration": "1.0"}})

    def test_probe_rejects_more_than_two_channels(self) -> None:
        with self.assertRaisesRegex(ValueError, "metadata"):
            parse_audio_ffprobe_json({"streams": [{"codec_type": "audio", "codec_name": "pcm", "sample_rate": "44100", "channels": 6, "sample_fmt": "s16", "duration": "1"}]})


if __name__ == "__main__":
    unittest.main()
