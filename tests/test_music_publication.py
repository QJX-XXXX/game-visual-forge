import json
import tempfile
import unittest
import hashlib
from pathlib import Path
from tests._bootstrap import ROOT  # noqa: F401
from tests.test_music_processing import write_wav
from tests.test_music_contract import music_request
from game_visual_forge.contracts.music import MusicProcessingResult, MusicSourceRecord
from game_visual_forge.quality.music import assess_music_outputs, record_music_review, publish_music_bundle
from game_visual_forge.contracts.music_review import REQUIRED_MUSIC_CHECKS


class MusicPublicationTests(unittest.TestCase):
    def test_publish_requires_listening_review_and_optional_unity_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); path = root / "track.wav"; write_wav(path, rate=44100, channels=2, seconds=1)
            source = MusicSourceRecord("track.wav", hashlib.sha256(path.read_bytes()).hexdigest(), "wav", 44100, 2, 1, "local", "a", "c")
            request = music_request(usage="bgm-linear", unity_import_requested=True)
            processing = MusicProcessingResult(source.sha256, str(path), "b" * 64, "c" * 64, 44100, 2, 1, 44100, 2)
            quality = assess_music_outputs(request, source, processing, repo_root=root)
            with self.assertRaises(ValueError):
                publish_music_bundle(root, request, processing, quality, None, root / "final")
            review = record_music_review(request, processing, quality, {key: True for key in REQUIRED_MUSIC_CHECKS}, now="2026-10-10T00:00:00Z", repo_root=root)
            out = publish_music_bundle(root, request, processing, quality, review, root / "final")
            self.assertEqual(out["unity_manifest"]["profile"], "music")
            self.assertEqual(out["unity_manifest"]["importer"]["load_type"], "Streaming")
            self.assertNotIn("AudioSource", json.dumps(out))


if __name__ == "__main__": unittest.main()
