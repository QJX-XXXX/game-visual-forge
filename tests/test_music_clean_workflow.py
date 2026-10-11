import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from tests._bootstrap import ROOT  # noqa: F401
from tests.test_music_processing import write_wav
from tests.test_music_contract import music_request
from game_visual_forge.contracts.music import MusicProcessingOptions, build_music_prompt_package, generation_fingerprint
from game_visual_forge.contracts.music_provider import MusicProvider, MusicProviderReceipt, default_music_capabilities
from game_visual_forge.contracts.serialization import dump_json
from game_visual_forge.providers.music import prepare_music_attempt, begin_music_submission, record_music_receipt
from game_visual_forge.processing.music import ingest_music_source, process_music_candidate
from game_visual_forge.quality.music import assess_music_outputs, record_music_review, publish_music_bundle
from game_visual_forge.contracts.music_review import REQUIRED_MUSIC_CHECKS


class CleanMusicWorkflowTests(unittest.TestCase):
    def test_pure_instrumental_local_source_to_publish(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); raw = root / "inputs" / "piano.wav"; raw.parent.mkdir(); write_wav(raw, rate=32000, channels=1, seconds=1.5)
            request = music_request(asset_id="solo-piano", usage="standalone-instrumental", unity_import_requested=True)
            cap = default_music_capabilities(local_ready=True)[MusicProvider.COMFYUI_MUSIC3]
            prompt = build_music_prompt_package(request, MusicProvider.COMFYUI_MUSIC3, "Solo piano study")
            attempt = prepare_music_attempt(request, prompt, cap, {"seed": 7}, now="2026-10-10T00:00:00Z")
            attempt_path = root / "attempt.json"; dump_json(attempt_path, attempt.to_dict())
            begin_music_submission(attempt_path, None, now="2026-10-10T00:00:00Z")
            record_music_receipt(attempt_path, MusicProviderReceipt("completed", "local-prompt-1", ("candidate-1",), returned_candidate_count=1), now="2026-10-10T00:00:00Z")
            source = ingest_music_source(root, raw, attempt, Path("unused"))
            processing = process_music_candidate(root, source, MusicProcessingOptions(), Path("unused"), Path("unused"))
            quality = assess_music_outputs(request, source, processing, repo_root=root)
            self.assertEqual(quality.status, "passed")
            review = record_music_review(request, processing, quality, {key: True for key in REQUIRED_MUSIC_CHECKS}, "2026-10-10T00:00:00Z", root)
            published = publish_music_bundle(root, request, processing, quality, review, root / "final")
            self.assertTrue((root / "final" / "solo-piano.wav").exists())
            self.assertEqual(published["unity_manifest"]["profile"], "music")

            changed = replace(MusicProcessingOptions(), loop_start_seconds=0.1, loop_end_seconds=0.8)
            self.assertEqual(processing.processing_fingerprint != process_music_candidate(root, source, changed, Path("unused"), Path("unused")).processing_fingerprint, True)
            self.assertEqual(generation_fingerprint(request, prompt, cap, {"seed": 7}), generation_fingerprint(request, prompt, cap, {"seed": 7}))


if __name__ == "__main__": unittest.main()
