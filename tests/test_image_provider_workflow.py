from __future__ import annotations

import base64
import json
import os
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from tests._bootstrap import ROOT  # noqa: F401
from tests.test_image_api_providers import FakeImageTransport, png_bytes
from tests.test_sprite_contract import make_request
from game_visual_forge.contracts import JobState, JobStatus, SpriteSourcePreference
from game_visual_forge.contracts.serialization import dump_json, load_json
from game_visual_forge.jobs import fingerprint_request, select_image_source
from game_visual_forge.providers.image import (
    confirm_image_attempt, download_image_attempt, prepare_image_attempt,
    query_image_attempt, submit_image_attempt,
)


NOW = "2026-11-17T00:00:00Z"


class ImageProviderWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.request = replace(make_request(), source_preference=SpriteSourcePreference.AUTO, reference_paths=(), seed_frame_path=None)
        self.request_path = self.root / "sprite-request.json"
        self.decision_path = self.root / "decision.json"
        self.parameters_path = self.root / "parameters.json"
        self.attempt_path = self.root / "attempt.json"
        self.confirmation_path = self.root / "confirmation.json"
        self.quote_path = self.root / "quote.json"
        self.state_path = self.root / "job-state.json"

    def prepare(self, provider="minimax", model="MiniMax-H3-Image", parameters=None, transport=None, quantity=1):
        fingerprint = fingerprint_request(self.request.to_dict())
        dump_json(self.request_path, self.request.to_dict())
        dump_json(self.decision_path, {"schema_version": 1, "request_fingerprint": fingerprint, "source_type": provider, "selected_provider": provider, "requires_user_selection": False, "requires_paid_confirmation": True})
        dump_json(self.parameters_path, parameters or {"prompt": "a complete sprite sheet", "size": "1024x1024"})
        dump_json(self.state_path, JobState(1, "job", self.request.asset_id, JobStatus.AWAITING_CONFIRMATION, NOW, NOW, fingerprint, provider=provider).to_dict())
        return prepare_image_attempt(self.request_path, self.decision_path, self.parameters_path, self.attempt_path, kind="sprite", model=model, quantity=quantity, repo_root=self.root, state_path=self.state_path, now=NOW, transport=transport)

    def confirm(self, provider="minimax"):
        dump_json(self.quote_path, {"schema_version": 1, "provider": provider, "currency": "CNY", "amount": "0.20", "verified": True, "notice": "user verified account estimate"})
        return confirm_image_attempt(self.attempt_path, self.quote_path, self.confirmation_path, now=NOW)

    def test_minimax_saves_png_and_only_then_releases_normal_ingest(self):
        self.prepare()
        self.confirm()
        image = png_bytes()
        transport = FakeImageTransport([{"data": [{"b64_json": base64.b64encode(image).decode()}]}])
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "private-key"}):
            result = submit_image_attempt(self.attempt_path, self.confirmation_path, repo_root=self.root, now=NOW, transport=transport)
        self.assertEqual(result["status"], "downloaded")
        self.assertTrue(load_json(self.confirmation_path)["consumed_at"])
        result = download_image_attempt(self.attempt_path, repo_root=self.root, now=NOW, transport=transport)
        self.assertEqual(load_json(self.state_path)["status"], "ready")
        self.assertEqual((self.root / result["outputs"][0]["path"]).read_bytes(), image)
        all_json = "".join(path.read_text() for path in self.root.rglob("*.json"))
        self.assertNotIn("private-key", all_json)
        self.assertNotIn("b64_json", all_json)
        with self.assertRaises(ValueError):
            submit_image_attempt(self.attempt_path, self.confirmation_path, repo_root=self.root, now=NOW, transport=transport)
        self.assertEqual(len(transport.calls), 1)

    def test_changed_parameters_and_references_fail_before_spend(self):
        reference = self.root / "hero.png"
        reference.write_bytes(png_bytes())
        self.prepare(parameters={"prompt": "edit hero", "size": "1024x1024", "references": [{"path": "hero.png"}]})
        self.confirm()
        reference.write_bytes(png_bytes(color="blue"))
        transport = FakeImageTransport()
        with self.assertRaisesRegex(ValueError, "reference changed"):
            submit_image_attempt(self.attempt_path, self.confirmation_path, repo_root=self.root, now=NOW, transport=transport)
        self.assertIsNone(load_json(self.confirmation_path)["consumed_at"])
        self.assertEqual(transport.calls, [])
        attempt = load_json(self.attempt_path)
        attempt["parameters"]["region"] = "global"
        dump_json(self.attempt_path, attempt)
        with self.assertRaisesRegex(ValueError, "binding"):
            submit_image_attempt(self.attempt_path, self.confirmation_path, repo_root=self.root, now=NOW, transport=transport)

    def test_switching_back_to_native_blocks_prepared_api_submission(self):
        self.prepare()
        self.confirm()
        state = JobState.from_dict(load_json(self.state_path))
        dump_json(self.state_path, select_image_source(state, None, now=NOW).to_dict())
        transport = FakeImageTransport()
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "secret"}), self.assertRaisesRegex(ValueError, "workflow source"):
            submit_image_attempt(self.attempt_path, self.confirmation_path, repo_root=self.root, now=NOW, transport=transport)
        self.assertIsNone(load_json(self.confirmation_path)["consumed_at"])
        self.assertEqual(transport.calls, [])

    def test_unknown_sync_submission_is_never_retried(self):
        self.prepare()
        self.confirm()
        transport = FakeImageTransport([TimeoutError()])
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "secret"}):
            result = submit_image_attempt(self.attempt_path, self.confirmation_path, repo_root=self.root, now=NOW, transport=transport)
        self.assertEqual(result["status"], "submission_unknown")
        with self.assertRaises(ValueError):
            submit_image_attempt(self.attempt_path, self.confirmation_path, repo_root=self.root, now=NOW, transport=transport)
        with self.assertRaisesRegex(ValueError, "synchronous"):
            query_image_attempt(self.attempt_path, repo_root=self.root, now=NOW, transport=transport)
        self.assertEqual(len(transport.calls), 1)

    def test_async_result_urls_are_used_only_in_memory(self):
        self.prepare("wanxiang", "wan2.7-image", {"prompt": "sprite", "size": "1K", "region": "cn-beijing", "workspace_id": "ws-1"})
        self.confirm("wanxiang")
        url = "https://result.invalid/image.png?Signature=transient-secret"
        transport = FakeImageTransport([
            {"output": {"task_id": "task-1"}},
            {"output": {"task_status": "SUCCEEDED", "choices": [{"message": {"content": [{"type": "image", "image": url}]}}]}},
        ], {url: png_bytes()})
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "secret"}):
            submit_image_attempt(self.attempt_path, self.confirmation_path, repo_root=self.root, now=NOW, transport=transport)
            result = download_image_attempt(self.attempt_path, repo_root=self.root, now=NOW, transport=transport)
        self.assertEqual(result["status"], "downloaded")
        self.assertNotIn("transient-secret", json.dumps(load_json(self.attempt_path)))
        self.assertTrue(all("ws-1.cn-beijing.maas.aliyuncs.com" in call[1] for call in transport.calls))

    def test_concurrent_submits_send_one_post(self):
        self.prepare()
        self.confirm()
        entered, release = threading.Event(), threading.Event()
        class BlockingTransport(FakeImageTransport):
            def request(inner, *args, **kwargs):
                entered.set()
                release.wait(5)
                return super().request(*args, **kwargs)
        transport = BlockingTransport([{"data": [{"b64_json": base64.b64encode(png_bytes()).decode()}]}])
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "secret"}), ThreadPoolExecutor(2) as executor:
            future = executor.submit(submit_image_attempt, self.attempt_path, self.confirmation_path, repo_root=self.root, now=NOW, transport=transport)
            self.assertTrue(entered.wait(5))
            try:
                with self.assertRaises(ValueError):
                    submit_image_attempt(self.attempt_path, self.confirmation_path, repo_root=self.root, now=NOW, transport=transport)
            finally:
                release.set()
            self.assertEqual(future.result()["status"], "downloaded")
        self.assertEqual(len(transport.calls), 1)

    def test_partial_minimax_success_and_malformed_item_keep_saved_image(self):
        self.prepare(quantity=2)
        self.confirm()
        transport = FakeImageTransport([{"data": [{"b64_json": base64.b64encode(png_bytes()).decode()}, {"b64_json": "invalid"}]}])
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "secret"}):
            result = submit_image_attempt(self.attempt_path, self.confirmation_path, repo_root=self.root, now=NOW, transport=transport)
        self.assertEqual(result["status"], "submission_unknown")
        self.assertEqual(len(result["outputs"]), 1)
        self.assertTrue((self.root / result["outputs"][0]["path"]).is_file())

    def test_oversized_local_request_fails_before_confirmation_consumption(self):
        reference = self.root / "hero.png"
        reference.write_bytes(png_bytes())
        self.prepare(parameters={"prompt": "edit", "size": "1024x1024", "references": [{"path": "hero.png"}]})
        self.confirm()
        transport = FakeImageTransport()
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "secret"}), patch("game_visual_forge.providers.minimax_image.MAX_REQUEST_BYTES", 100):
            with self.assertRaisesRegex(ValueError, "request exceeds"):
                submit_image_attempt(self.attempt_path, self.confirmation_path, repo_root=self.root, now=NOW, transport=transport)
        self.assertIsNone(load_json(self.confirmation_path)["consumed_at"])
        self.assertEqual(transport.calls, [])

    def test_partial_download_can_resume_without_another_generation(self):
        self.prepare("wanxiang", "wan2.7-image", {"prompt": "sprite", "size": "1K"}, quantity=2)
        self.confirm("wanxiang")
        urls = ["https://result.invalid/1.png", "https://result.invalid/2.png"]
        completed = {"output": {"task_status": "SUCCEEDED", "choices": [{"message": {"content": [{"type": "image", "image": url} for url in urls]}}]}}
        transport = FakeImageTransport([{"output": {"task_id": "task"}}, completed, completed], {urls[0]: png_bytes(), urls[1]: TimeoutError()})
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "secret"}):
            submit_image_attempt(self.attempt_path, self.confirmation_path, repo_root=self.root, now=NOW, transport=transport)
            with self.assertRaises(TimeoutError):
                download_image_attempt(self.attempt_path, repo_root=self.root, now=NOW, transport=transport)
            self.assertEqual(len(load_json(self.attempt_path)["outputs"]), 1)
            transport.images[urls[1]] = png_bytes(color="blue")
            result = download_image_attempt(self.attempt_path, repo_root=self.root, now=NOW, transport=transport)
        self.assertEqual(result["status"], "downloaded")
        self.assertEqual([call[0] for call in transport.calls], ["POST", "GET", "GET"])
        (self.root / result["outputs"][0]["path"]).write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "changed"):
            download_image_attempt(self.attempt_path, repo_root=self.root, now=NOW, transport=transport)

    def test_manual_async_task_id_survives_query_timeout(self):
        self.prepare("wanxiang", "wan2.7-image", {"prompt": "sprite", "size": "1K"})
        self.confirm("wanxiang")
        transport = FakeImageTransport([TimeoutError(), TimeoutError(), {"output": {"task_status": "FAILED", "code": "ContentRejected"}}])
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "secret"}):
            submit_image_attempt(self.attempt_path, self.confirmation_path, repo_root=self.root, now=NOW, transport=transport)
            with self.assertRaises(TimeoutError):
                query_image_attempt(self.attempt_path, repo_root=self.root, now=NOW, transport=transport, recovered_task_id="recovered-1")
            self.assertEqual(load_json(self.attempt_path)["external_task_id"], "recovered-1")
            result = query_image_attempt(self.attempt_path, repo_root=self.root, now=NOW, transport=transport)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_code"], "ContentRejected")

    def test_invalid_quote_and_source_binding_do_not_authorize_generation(self):
        self.prepare()
        dump_json(self.quote_path, {"schema_version": 1, "provider": "minimax", "currency": "CNY", "amount": "NaN", "verified": True, "notice": "invalid"})
        with self.assertRaises(ValueError):
            confirm_image_attempt(self.attempt_path, self.quote_path, self.confirmation_path, now=NOW)
        self.assertFalse(self.confirmation_path.exists())

    def test_subsequent_candidate_can_link_ready_parent_job(self):
        self.prepare()
        state = load_json(self.state_path)
        state["status"] = "ready"
        dump_json(self.state_path, state)
        result = prepare_image_attempt(self.request_path, self.decision_path, self.parameters_path, self.root / "candidate-2.json", kind="sprite", model="MiniMax-H3-Image", quantity=1, repo_root=self.root, state_path=self.state_path, now=NOW)
        self.assertEqual(result["status"], "prepared")

    def test_invalid_decoded_image_does_not_discard_later_valid_image(self):
        self.prepare(quantity=2)
        self.confirm()
        transport = FakeImageTransport([{"data": [{"b64_json": base64.b64encode(data).decode()} for data in (b"not an image", png_bytes())]}])
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "secret"}):
            result = submit_image_attempt(self.attempt_path, self.confirmation_path, repo_root=self.root, now=NOW, transport=transport)
        self.assertEqual(result["status"], "submission_unknown")
        self.assertEqual([item["index"] for item in result["outputs"]], [2])
        self.assertEqual(result["errors"][0]["index"], 1)

    def test_single_save_failure_retains_pending_image_and_saves_other_items(self):
        self.prepare(quantity=2)
        self.confirm()
        transport = FakeImageTransport([{"data": [{"b64_json": base64.b64encode(png_bytes(color=color)).decode()} for color in ("red", "blue")]}])
        original_replace = os.replace
        def fail_first_candidate(source, destination):
            if Path(destination).name == "candidate-01.png":
                raise OSError("simulated rename failure")
            return original_replace(source, destination)
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "secret"}), patch("game_visual_forge.providers.image.os.replace", side_effect=fail_first_candidate):
            result = submit_image_attempt(self.attempt_path, self.confirmation_path, repo_root=self.root, now=NOW, transport=transport)
        self.assertEqual([item["index"] for item in result["outputs"]], [2])
        self.assertTrue((self.root / result["output_dir"] / ".candidate-01.part").is_file())
        recovered = download_image_attempt(self.attempt_path, repo_root=self.root, now=NOW, transport=transport)
        self.assertEqual(recovered["status"], "downloaded")
        self.assertEqual(sorted(item["index"] for item in recovered["outputs"]), [1, 2])
        self.assertEqual(len(transport.calls), 1)

    def test_saved_file_survives_interrupted_receipt_write(self):
        self.prepare()
        self.confirm()
        transport = FakeImageTransport([{"data": [{"b64_json": base64.b64encode(png_bytes()).decode()}]}])
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "secret"}):
            result = submit_image_attempt(self.attempt_path, self.confirmation_path, repo_root=self.root, now=NOW, transport=transport)
        result.update(status="submitting", outputs=[])
        dump_json(self.attempt_path, result)
        recovered = download_image_attempt(self.attempt_path, repo_root=self.root, now=NOW, transport=transport)
        self.assertEqual(recovered["status"], "downloaded")
        self.assertEqual(len(recovered["outputs"]), 1)

    def test_malformed_async_receipts_keep_task_id_and_can_query(self):
        cases = [
            ("jimeng", "jimeng_t2i_v40", {"data": {"task_id": "task-1"}}),
            ("jimeng", "jimeng_t2i_v40", {"code": None, "data": {"task_id": "task-1"}}),
            ("wanxiang", "wan2.7-image", {"code": "ServiceUnavailable", "output": {"task_id": "task-1"}}),
            ("wanxiang", "wan2.7-image", {"output": {"task_id": "task-1", "task_status": 123}}),
            ("wanxiang", "wan2.7-image", {"output": {"task_id": "task-1", "task_status": []}}),
        ]
        for index, (provider, model, response) in enumerate(cases):
            with self.subTest(response=response):
                self.attempt_path = self.root / f"attempt-{index}.json"
                self.confirmation_path = self.root / f"confirmation-{index}.json"
                parameters = {"prompt": "sprite", "size": 1024 ** 2 if provider == "jimeng" else "1K"}
                self.prepare(provider, model, parameters)
                self.confirm(provider)
                terminal = {"code": 10000, "data": {"status": "expired"}} if provider == "jimeng" else {"output": {"task_status": "FAILED"}}
                transport = FakeImageTransport([response, terminal])
                with patch.dict(os.environ, {"JIMENG_ACCESS_KEY": "ak", "JIMENG_SECRET_KEY": "sk", "DASHSCOPE_API_KEY": "key"}):
                    result = submit_image_attempt(self.attempt_path, self.confirmation_path, repo_root=self.root, now=NOW, transport=transport)
                    self.assertEqual(result["status"], "submission_unknown")
                    self.assertEqual(result["external_task_id"], "task-1")
                    self.assertEqual(query_image_attempt(self.attempt_path, repo_root=self.root, now=NOW, transport=transport)["status"], "failed")

    def test_unrecognized_async_error_without_id_is_unknown(self):
        self.prepare("wanxiang", "wan2.7-image", {"prompt": "sprite", "size": "1K"})
        self.confirm("wanxiang")
        transport = FakeImageTransport([{"code": "ServiceUnavailable"}])
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "key"}):
            result = submit_image_attempt(self.attempt_path, self.confirmation_path, repo_root=self.root, now=NOW, transport=transport)
        self.assertEqual(result["status"], "submission_unknown")


if __name__ == "__main__":
    unittest.main()
