from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests._bootstrap import ROOT  # noqa: F401
from tests.test_audio_contract import valid_audio_request
from tests.test_audio_ingest import write_pcm_wav

from game_visual_forge.cli.audio import run_audio_plan
from game_visual_forge.cli.audio import run_audio_provider_preflight_command, run_audio_route, run_audio_generate, run_audio_process, run_audio_record_review, run_audio_validate
from game_visual_forge.contracts.audio import AudioRequest, audio_confirmation_sha256
from game_visual_forge.contracts.audio_review import REQUIRED_AUDIO_CHECKS


class AudioCleanWorkflowTests(unittest.TestCase):
    def test_unconfirmed_plan_writes_no_execution_or_job_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request = root / "request.json"
            request.write_text(json.dumps(valid_audio_request(), ensure_ascii=False), encoding="utf-8")
            result = run_audio_plan(request, root / "run", "2026-08-14T00:00:00Z")
            self.assertEqual(result["status"], "needs_user_confirmation")
            self.assertFalse((root / "run" / "execution-plan.json").exists())
            self.assertFalse((root / "run" / "job-state.json").exists())

    def test_confirmed_plan_writes_only_planned_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = valid_audio_request()
            payload["confirmed_sha256"] = audio_confirmation_sha256(AudioRequest.from_dict(payload))
            request = root / "request.json"
            request.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            result = run_audio_plan(request, root / "run", "2026-08-14T00:00:00Z")
            self.assertEqual(result["status"], "planned")
            self.assertTrue((root / "run" / "execution-plan.json").is_file())
            self.assertTrue((root / "run" / "job-state.json").is_file())

    def test_clean_fake_provider_workflow_publishes_selected_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = valid_audio_request(duration_seconds=1.0)
            payload["confirmed_sha256"] = audio_confirmation_sha256(AudioRequest.from_dict(payload))
            request_path = root / "request.json"
            request_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            run_dir = root / "run"
            run_audio_plan(request_path, run_dir, "2026-08-14T00:00:00Z")
            fake = ROOT / "tests" / "fixtures" / "fake_audio_provider.py"
            preflight_payload = root / "preflight-request.json"
            preflight_payload.write_text("{}", encoding="utf-8")
            preflight_path = root / "preflight.json"
            run_audio_provider_preflight_command(fake, preflight_payload, preflight_path)
            run_audio_route(request_path, preflight_path, root / "decision.json", run_dir / "job-state.json", "2026-08-14T00:01:00Z")
            generation = run_audio_generate(request_path, root / "decision.json", None, fake, root, run_dir, run_dir / "job-state.json", "2026-08-14T00:02:00Z")
            processing = run_audio_process(request_path, run_dir / "generation-result.json", None, root, run_dir, run_dir / "job-state.json", "2026-08-14T00:03:00Z", ROOT / "tests" / "fixtures" / "fake_audio_ffmpeg.py", ROOT / "tests" / "fixtures" / "fake_audio_ffprobe.py")
            checks_path = root / "checks.json"
            checks_path.write_text(json.dumps({key: True for key in REQUIRED_AUDIO_CHECKS}), encoding="utf-8")
            run_audio_record_review(request_path, run_dir / "generation-result.json", run_dir / "processing-result.json", root / "quality-report.json", checks_path, "candidate-01", root, root / "review.json", "2026-08-14T00:04:00Z")
            result = run_audio_validate(request_path, run_dir / "generation-result.json", run_dir / "processing-result.json", root / "review.json", root / "quality-report.json", root, root / "final", "2026-08-14T00:05:00Z")
            self.assertEqual(result["status"], "completed")
            self.assertTrue((root / "final" / "iron-sword-hit.wav").is_file())
            self.assertTrue((root / "final" / "audio-manifest.json").is_file())
            self.assertTrue((root / "final" / "unity-audio-manifest.json").is_file())
            self.assertFalse((root / "final" / "audio-source-placement.json").exists())


if __name__ == "__main__":
    unittest.main()
