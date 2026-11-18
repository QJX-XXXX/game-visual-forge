from __future__ import annotations

import contextlib
import importlib.metadata
import io
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from tests._bootstrap import ROOT
from tests.test_image_api_providers import FakeImageTransport, png_bytes
from tests import test_image_provider_workflow as image_workflow
from tests.test_image_provider_workflow import NOW
from game_visual_forge.cli.main import main
from game_visual_forge.contracts.serialization import dump_json, load_json
from game_visual_forge.providers.image import download_image_attempt, image_adapter, submit_image_attempt
from game_visual_forge.providers.image_http import ImageApiError
from game_visual_forge.providers.mcp_client import McpClient, tool_result
from game_visual_forge.providers.tool_runtime import execution_config, existing_command, run_tool, tool_preflight


class ProviderToolTests(unittest.TestCase):
    def setUp(self):
        self.workflow = image_workflow.ImageProviderWorkflowTests()
        self.workflow.setUp()
        self.addCleanup(self.workflow.doCleanups)
        self.root = self.workflow.root
        self.script = self.root / "fake_vendor.py"
        self.script.write_text(
            "import json,sys,base64\nfrom pathlib import Path\n"
            "args=sys.argv[1:]\n"
            "if '-h' in args:\n print('--prompt --images --image --ratio --duration --resolution_type');sys.exit()\n"
            "if args[0] in ('text2image','image2image','text2video','image2video'):\n print(json.dumps({'submit_id':'dream-task','gen_status':'querying'}));sys.exit()\n"
            "if args[0]=='query_result':\n"
            " directory=next((a.split('=',1)[1] for a in args if a.startswith('--download_dir=')),None)\n"
            " if directory:\n  output=Path(directory)/'result.png';output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(base64.b64decode('" + __import__("base64").b64encode(png_bytes()).decode() + "'))\n"
            " print(json.dumps({'gen_status':'success','submit_id':'dream-task'}));sys.exit()\n"
            "if args[:2]==['video','generate']:\n print(json.dumps({'taskId':'mmx-task'}));sys.exit()\n"
            "if args[:3]==['video','task','get']:\n print(json.dumps({'status':'succeeded','url':'https://example.test/video.mp4'}));sys.exit()\n"
            "directory=Path(args[args.index('--out-dir')+1]);directory.mkdir(parents=True,exist_ok=True)\n"
            "output=directory/'result.png';output.write_bytes(base64.b64decode('" + __import__("base64").b64encode(png_bytes()).decode() + "'))\n"
            "print(json.dumps({'saved':[str(output)],'success_count':1,'total':1}))\n",
            encoding="utf-8",
        )
        self.execution = {"backend": "cli", "command": [sys.executable, str(self.script)]}

    def test_installed_cli_image_lifecycle_for_all_three_providers(self):
        for provider, model in (("minimax", "MiniMax-H3-Image"), ("wanxiang", "wan2.7-image"), ("jimeng", "dreamina-default")):
            with self.subTest(provider=provider):
                for path in (self.workflow.attempt_path, self.workflow.confirmation_path):
                    path.unlink(missing_ok=True)
                self.workflow.prepare(provider, model, {"prompt": "完整精灵图", "execution": self.execution})
                self.workflow.confirm(provider)
                receipt = submit_image_attempt(self.workflow.attempt_path, self.workflow.confirmation_path, repo_root=self.root, now=NOW)
                self.assertIn(receipt["status"], {"submitted", "downloaded"})
                result = download_image_attempt(self.workflow.attempt_path, repo_root=self.root, now=NOW)
                self.assertEqual(result["status"], "downloaded")
                self.assertEqual((self.root / result["outputs"][0]["path"]).read_bytes(), png_bytes())
                with self.assertRaises(ValueError):
                    submit_image_attempt(self.workflow.attempt_path, self.workflow.confirmation_path, repo_root=self.root, now=NOW)

    def test_cli_choice_is_bound_to_paid_confirmation(self):
        self.workflow.prepare(parameters={"prompt": "hero", "execution": self.execution})
        self.workflow.confirm()
        attempt = load_json(self.workflow.attempt_path)
        attempt["parameters"]["execution"]["command"] = ["different-tool"]
        dump_json(self.workflow.attempt_path, attempt)
        with self.assertRaisesRegex(ValueError, "binding"):
            download_image_attempt(self.workflow.attempt_path, repo_root=self.root, now=NOW)
        self.assertIsNone(load_json(self.workflow.confirmation_path)["consumed_at"])

    def test_missing_cli_does_not_consume_confirmation_or_install(self):
        self.workflow.prepare(parameters={"prompt": "hero", "execution": {"backend": "cli", "command": ["gvf-missing-tool"]}})
        self.workflow.confirm()
        with patch("subprocess.run") as run:
            with self.assertRaisesRegex(ValueError, "missing"):
                submit_image_attempt(self.workflow.attempt_path, self.workflow.confirmation_path, repo_root=self.root, now=NOW)
        run.assert_not_called()
        self.assertIsNone(load_json(self.workflow.confirmation_path)["consumed_at"])
        report = tool_preflight("minimax", execution_config("minimax", {"backend": "cli", "command": ["gvf-missing-tool"]}))
        self.assertTrue(report["requires_installation_confirmation"])
        self.assertFalse(report["authenticated"])

    def test_generation_rejects_installing_launchers(self):
        for command in (["uvx", "minimax-mcp"], ["npx", "some-server"], ["powershell", "installer.ps1"], [sys.executable, "-m", "pip", "install", "pkg"]):
            with self.subTest(command=command), patch("subprocess.run") as run:
                with self.assertRaises(ValueError):
                    existing_command(command)
                run.assert_not_called()

    def test_cli_models_do_not_claim_highspeed_support(self):
        adapter = image_adapter("minimax", execution=self.execution)
        self.assertEqual([item["model"] for item in adapter.models()["models"]], ["MiniMax-H3-Image"])
        adapter.normalize("MiniMax-H3-Image", {"prompt": "hero", "area": "4K"}, 2)
        with self.assertRaises(ValueError):
            image_adapter("minimax").normalize("MiniMax-H3-Image", {"prompt": "hero", "area": "4K"}, 2)

    def test_cli_argv_uses_region_and_exclusive_h3_size(self):
        adapter = image_adapter("minimax", execution=self.execution, repo_root=self.root)
        params = adapter.normalize("MiniMax-H3-Image", {"prompt": "hero", "area": "2K"}, 1)
        with patch("game_visual_forge.providers.tool_images.run_tool", return_value={"saved": []}) as run:
            with self.assertRaises(ImageApiError):
                adapter.submit("MiniMax-H3-Image", params, 1, [])
        arguments = run.call_args.args[1]
        self.assertNotIn("--size", arguments)
        self.assertIn("--area", arguments)
        self.assertIn("--region", arguments)
        self.assertIn("--base-url", arguments)

    def test_synchronous_cli_output_recovers_after_json_loss(self):
        attempt = self.workflow.prepare(parameters={"prompt": "hero", "execution": self.execution})
        self.workflow.confirm()
        directory = self.root / attempt["output_dir"] / ".provider"
        directory.mkdir(parents=True)
        (directory / "vendor-output.png").write_bytes(png_bytes())
        attempt["status"] = "submission_unknown"
        dump_json(self.workflow.attempt_path, attempt)
        with patch("subprocess.run") as run:
            result = download_image_attempt(self.workflow.attempt_path, repo_root=self.root, now=NOW)
        run.assert_not_called()
        self.assertEqual(result["status"], "downloaded")

    def test_dreamina_help_mismatch_fails_before_consuming_confirmation(self):
        self.workflow.prepare("jimeng", "dreamina-default", {"prompt": "hero", "execution": self.execution})
        self.workflow.confirm("jimeng")
        response = subprocess.CompletedProcess([], 0, "--unsupported", "")
        with patch("subprocess.run", return_value=response):
            with self.assertRaisesRegex(ValueError, "required flags"):
                submit_image_attempt(self.workflow.attempt_path, self.workflow.confirmation_path, repo_root=self.root, now=NOW)
        self.assertIsNone(load_json(self.workflow.confirmation_path)["consumed_at"])

    def test_cli_preflight_entry_point_reports_setup(self):
        output = io.StringIO()
        with patch("shutil.which", return_value=None), contextlib.redirect_stdout(output):
            code = main(["image", "provider", "preflight", "--provider", "wanxiang", "--backend", "cli"])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(output.getvalue())["requires_installation_confirmation"])

    def test_normal_source_route_accepts_tool_readiness_without_claiming_authentication(self):
        from dataclasses import replace
        from game_visual_forge.contracts import ProviderPreflight, SourceType
        from game_visual_forge.routing import AgentImageCapabilities, route_sprite
        report = tool_preflight("minimax", execution_config("minimax", self.execution))
        preflight = ProviderPreflight.from_dict(report)
        self.assertFalse(preflight.authenticated)
        self.assertEqual(preflight.to_dict()["backend"], "cli")
        decision = route_sprite(self.workflow.request, AgentImageCapabilities(False, ()), selected_source=SourceType.MINIMAX, provider_preflight=preflight)
        self.assertFalse(decision.requires_user_selection)
        self.assertTrue(decision.requires_paid_confirmation)
        self.assertEqual(decision.selected_backend, "cli")
        from game_visual_forge.contracts import MapSourceDecision
        with self.assertRaisesRegex(ValueError, "backend"):
            MapSourceDecision.from_dict({**decision.to_dict(), "selected_backend": "invalid"})
        self.workflow.prepare(parameters={"prompt": "hero", "execution": self.execution})
        dump_json(self.workflow.decision_path, decision.to_dict())
        inherited_path = self.root / "inherited-attempt.json"
        inherited_parameters = self.root / "inherited-parameters.json"
        dump_json(inherited_parameters, {"prompt": "hero"})
        from game_visual_forge.providers.image import prepare_image_attempt
        inherited = prepare_image_attempt(self.workflow.request_path, self.workflow.decision_path, inherited_parameters, inherited_path, kind="sprite", model="MiniMax-H3-Image", quantity=1, repo_root=self.root, now=NOW)
        self.assertEqual(inherited["parameters"]["execution"]["backend"], "cli")
        with self.assertRaisesRegex(ValueError, "selected source"):
            prepare_image_attempt(self.workflow.request_path, self.workflow.decision_path, inherited_parameters, self.root / "conflicting-attempt.json", kind="sprite", model="MiniMax-H3-Image", quantity=1, repo_root=self.root, now=NOW, execution={"backend": "mcp"})
        failed = replace(preflight, authentication_verified=True)
        decision = route_sprite(self.workflow.request, AgentImageCapabilities(False, ()), selected_source=SourceType.MINIMAX, provider_preflight=failed)
        self.assertTrue(decision.requires_user_selection)

    def test_vendor_stderr_is_not_exposed(self):
        response = subprocess.CompletedProcess([], 1, "", "Bearer private-token")
        with patch("subprocess.run", return_value=response):
            with self.assertRaises(ImageApiError) as caught:
                run_tool(execution_config("minimax", self.execution), ["image", "generate"])
        self.assertNotIn("private-token", str(caught.exception))

    def test_existing_video_wrappers_dispatch_cli_and_preserve_backend(self):
        from game_visual_forge.providers.minimax_video import run_command as minimax
        from game_visual_forge.providers.jimeng_video import run_command as jimeng
        for run, provider, model in ((minimax, "minimax", "MiniMax-H3"), (jimeng, "jimeng", "dreamina-default")):
            payload = {"backend": "cli", "model": model, "mode": "t2v", "parameters": {"prompt": "hero walking", "execution": self.execution}}
            with self.subTest(provider=provider), patch("urllib.request.urlopen", side_effect=AssertionError("unexpected HTTP generation")):
                receipt = run("submit", payload)
                self.assertEqual(receipt["backend"], "cli")
                query = run("query", {**payload, "external_task_id": receipt["external_task_id"]})
                self.assertEqual(query["backend"], "cli")
                self.assertEqual(query["status"], "completed")

    def test_video_cli_prepare_confirm_submit_query_download(self):
        from game_visual_forge.contracts import CostEstimate, ExternalProvider, VideoGenerationMode, VideoGenerationAttempt
        from game_visual_forge.contracts.video_provider import VideoAttemptStatus, VideoPaidConfirmation, VideoProviderBackend
        from game_visual_forge.providers.minimax_video import run_command
        from game_visual_forge.providers.video import submit_video_attempt, query_video_attempt, download_video_attempt
        payload = {"backend": "cli", "region": "cn", "model": "MiniMax-H3", "mode": "t2v", "parameters": {"prompt": "hero walking", "execution": self.execution}}
        snapshot = run_command("models", payload)
        self.assertEqual(snapshot["backend"], "cli")
        self.assertEqual([item["model"] for item in snapshot["models"]], ["MiniMax-H3"])
        prepared = run_command("prepare", {**payload, "snapshot": snapshot})
        attempt = VideoGenerationAttempt(1, "video-cli", "b" * 64, ExternalProvider.MINIMAX, VideoProviderBackend.CLI, "cn", "MiniMax-H3", snapshot["snapshot_sha256"], prepared["parameters"], VideoAttemptStatus.PREPARED, NOW, NOW)
        confirmation = VideoPaidConfirmation.create(attempt_id=attempt.attempt_id, provider=attempt.provider, backend=attempt.backend, region=attempt.region, model=attempt.model, model_snapshot_sha256=attempt.model_snapshot_sha256, mode=VideoGenerationMode.T2V, parameters=attempt.parameters, reference_sha256=(), quantity=1, estimate=CostEstimate(1, attempt.provider, "CNY", "0.2", True, "verified"), request_fingerprint=attempt.request_fingerprint, confirmed_at=NOW)
        attempt_path = self.root / "job" / "video.json"
        confirmation_path = attempt_path.with_name("video-confirmation.json")
        dump_json(attempt_path, attempt.to_dict())
        dump_json(confirmation_path, confirmation.to_dict())
        calls = []

        def dispatch(executable, operation, value):
            calls.append((operation.value, value))
            return run_command(operation.value, value)

        def download(url, target):
            target.write_bytes(b"validated-by-later-video-ingest")

        with patch("game_visual_forge.providers.video._run", side_effect=dispatch), patch("game_visual_forge.providers.tool_video._download_url", side_effect=download):
            submitted = submit_video_attempt(attempt_path, confirmation_path, self.script, now=NOW)
            self.assertEqual(submitted.external_task_id, "mmx-task")
            self.assertEqual(query_video_attempt(attempt_path, self.script, now=NOW).status, VideoAttemptStatus.COMPLETED)
            downloaded = download_video_attempt(attempt_path, self.script, self.root / "video-output", now=NOW)
            self.assertEqual(downloaded.status, VideoAttemptStatus.DOWNLOADED)
            self.assertEqual(Path(downloaded.downloaded_path), self.root / "video-output" / "video.mp4")
            self.assertTrue(Path(downloaded.downloaded_path).is_file())
            count = len(calls)
            download_video_attempt(attempt_path, self.script, self.root / "video-output", now=NOW)
            self.assertEqual(query_video_attempt(attempt_path, self.script, now=NOW).status, VideoAttemptStatus.DOWNLOADED)
            self.assertEqual(len(calls), count)
        self.assertTrue(load_json(confirmation_path)["consumed_at"])
        self.assertTrue(all(value["backend"] == "cli" and value["parameters"]["execution"] == attempt.parameters["execution"] for _, value in calls))

        for status, expected in (("cancelled", VideoAttemptStatus.CANCELLED), ("expired", VideoAttemptStatus.FAILED)):
            with self.subTest(status=status), patch("game_visual_forge.providers.video._run", side_effect=dispatch), patch(
                "game_visual_forge.providers.tool_video.run_tool", return_value={"status": status},
            ):
                dump_json(attempt_path, submitted.to_dict())
                queried = query_video_attempt(attempt_path, self.script, now=NOW)
                self.assertEqual(queried.status, expected)
                if status == "expired":
                    self.assertEqual(queried.error_code, "expired")

    def test_video_downloads_keep_existing_other_attempt_output(self):
        from tests import test_video_provider_orchestration as video_tests
        from game_visual_forge.contracts import VideoGenerationAttempt
        from game_visual_forge.contracts.video_provider import VideoAttemptStatus
        from game_visual_forge.providers.video import download_video_attempt
        fixture = video_tests.VideoProviderOrchestrationTests()
        attempt_path, _, _ = fixture.setup_paths(self.root)
        original = VideoGenerationAttempt.from_dict(load_json(attempt_path)).replace(status=VideoAttemptStatus.SUBMITTED, external_task_id="task-1")
        dump_json(attempt_path, original.to_dict())
        directory = self.root / "video-output"
        directory.mkdir()
        (directory / "video.mp4").write_bytes(b"other-attempt")
        temporary_paths = []

        def download(executable, operation, payload):
            temporary = Path(payload["output_path"])
            temporary_paths.append(temporary)
            temporary.write_bytes(b"current-attempt")
            return {"schema_version": 1, "path": str(temporary)}

        with patch("game_visual_forge.providers.video._run", side_effect=download):
            result = download_video_attempt(attempt_path, self.script, directory, now=NOW)
        self.assertEqual((directory / "video.mp4").read_bytes(), b"other-attempt")
        self.assertEqual((self.root / result.downloaded_path).read_bytes(), b"current-attempt")
        self.assertNotEqual(temporary_paths[0].name, ".video-download.tmp")

    def test_official_minimax_video_mcp_dispatch_and_profile(self):
        from game_visual_forge.providers.minimax_video import run_command
        class Client:
            def call(self, name, arguments):
                if name == "generate_video":
                    text = "Success. Video generation task submitted: Task ID: mcp-video. Please use `query_video_generation` tool to check the status of the task and get the result."
                else:
                    text = "Success. Video URL: https://example.test/video.mp4"
                return {"content": [{"type": "text", "text": text}]}
        payload = {"backend": "mcp", "model": "MiniMax-Hailuo-02", "mode": "t2v", "parameters": {"prompt": "hero walking"}}
        with patch("game_visual_forge.providers.tool_video._mcp", return_value=Client()):
            result = run_command("submit", payload)
            self.assertEqual(result["backend"], "mcp")
            self.assertEqual(result["external_task_id"], "mcp-video")
            self.assertEqual(run_command("query", {**payload, "external_task_id": "mcp-video"})["status"], "completed")
            with self.assertRaisesRegex(ValueError, "verified"):
                run_command("submit", {**payload, "model": "MiniMax-H3"})

    def test_mcp_schema_mismatch_does_not_consume_confirmation(self):
        self.workflow.prepare(parameters={"prompt": "hero", "execution": {"backend": "mcp", "command": [sys.executable]}})
        self.workflow.confirm()
        class Client:
            def tools(self):
                return [{"name": "text_to_image", "inputSchema": {"required": ["new_required_parameter"]}}]
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "private-key"}), patch("game_visual_forge.providers.tool_images.McpClient", return_value=Client()):
            with self.assertRaisesRegex(ValueError, "schema"):
                submit_image_attempt(self.workflow.attempt_path, self.workflow.confirmation_path, repo_root=self.root, now=NOW)
        self.assertIsNone(load_json(self.workflow.confirmation_path)["consumed_at"])

    def test_mcp_connection_config_contains_environment_names(self):
        config = execution_config("wanxiang", {"backend": "mcp"})
        self.assertEqual(config["credential_env"], "DASHSCOPE_API_KEY")
        self.assertIn("TextGenerateImage/mcp", config["url"])
        for url in ("https://server.test/mcp?api_key=secret", "https://user:pass@server.test/mcp", "http://server.test/mcp"):
            with self.assertRaises(ValueError):
                execution_config("wanxiang", {"backend": "mcp", "url": url})

    def test_official_mcp_images_use_existing_confirmation_and_ingestion(self):
        class Client:
            def __init__(self, tool, text):
                self.tool, self.text, self.calls = tool, text, []
            def tools(self):
                return [{"name": self.tool, "inputSchema": {"type": "object", "required": ["prompt"]}}]
            def call(self, name, arguments):
                self.calls.append((name, arguments))
                return {"content": [{"type": "text", "text": self.text}]}

        for provider, model, tool, text in (("minimax", "MiniMax-H3-Image", "text_to_image", "Success. Image URLs: ['https://example.test/image.png']"), ("wanxiang", "bailian-image-auto", "bailian_image_gen", '{"results":["https://example.test/image.png"]}')):
            with self.subTest(provider=provider):
                for path in (self.workflow.attempt_path, self.workflow.confirmation_path):
                    path.unlink(missing_ok=True)
                config = {"backend": "mcp"}
                if provider == "minimax":
                    config["command"] = [sys.executable]
                self.workflow.prepare(provider, model, {"prompt": "hero", "execution": config})
                self.workflow.confirm(provider)
                client = Client(tool, text)
                transport = FakeImageTransport([], {"https://example.test/image.png": png_bytes()})
                with patch.dict(os.environ, {"MINIMAX_API_KEY": "private-token", "DASHSCOPE_API_KEY": "private-token"}), patch("game_visual_forge.providers.tool_images.McpClient", return_value=client):
                    result = submit_image_attempt(self.workflow.attempt_path, self.workflow.confirmation_path, repo_root=self.root, now=NOW, transport=transport)
                self.assertEqual(result["status"], "downloaded")
                self.assertEqual(client.calls[0][0], tool)
                if provider == "wanxiang":
                    self.assertNotIn("model", client.calls[0][1])
                self.assertNotIn("private-token", self.workflow.attempt_path.read_text())
                self.assertNotIn("https://example.test", self.workflow.attempt_path.read_text())

    @unittest.skipUnless(importlib.util.find_spec("mcp"), "optional MCP SDK unavailable")
    def test_real_stdio_bridge_discovery_and_readonly_call(self):
        if not importlib.metadata.version("mcp").startswith("2."):
            self.skipTest("MCP 2.x is required")
        config = execution_config("jimeng", {"backend": "mcp", "transport": "stdio", "command": [sys.executable, "-m", "game_visual_forge", "mcp", "serve", "--repo-root", str(self.root)], "timeout_seconds": 20})
        client = McpClient(config, environment={"PYTHONPATH": str(ROOT / "src")})
        tools = client.tools()
        self.assertIn("jimeng_image_submit", {item["name"] for item in tools})
        result = tool_result(client.call("jimeng_image_models", {}))
        self.assertEqual(result["provider"], "jimeng")
        self.assertEqual(result["backend"], "cli")
        self.workflow.prepare("jimeng", "jimeng_t2i_v40", {"prompt": "hero"})
        prepared = tool_result(client.call("jimeng_image_prepare", {"request": "sprite-request.json", "decision": "decision.json", "output": "bridge-api-attempt.json", "backend": "api", "now": NOW}))
        self.assertEqual(prepared["model"], "jimeng_t2i_v40")
        with self.assertRaises(ImageApiError):
            client.call("jimeng_image_confirm", {"attempt": "missing.json", "quote": "quote.json", "output": "confirmation.json", "now": NOW})

    @unittest.skipUnless(importlib.util.find_spec("mcp"), "optional MCP SDK unavailable")
    def test_real_wan_bridge_preserves_explicit_model_and_paid_confirmation(self):
        if not importlib.metadata.version("mcp").startswith("2."):
            self.skipTest("MCP 2.x is required")
        self.workflow.prepare("wanxiang", "wan2.7-image", {"prompt": "hero", "execution": self.execution})
        self.workflow.confirm("wanxiang")
        config = execution_config("wanxiang", {"backend": "mcp", "transport": "stdio", "command": [sys.executable, "-m", "game_visual_forge", "mcp", "serve", "--provider", "wanxiang", "--repo-root", str(self.root)], "timeout_seconds": 20})
        client = McpClient(config, environment={"PYTHONPATH": str(ROOT / "src")})
        names = {item["name"] for item in client.tools()}
        self.assertIn("wanxiang_image_submit", names)
        self.assertNotIn("jimeng_video_submit", names)
        prepared = tool_result(client.call("wanxiang_image_prepare", {"request": "sprite-request.json", "decision": "decision.json", "parameters": "parameters.json", "output": "wan-attempt.json", "model": "wan2.7-image", "now": NOW}))
        self.assertEqual(prepared["model"], "wan2.7-image")
        client.call("wanxiang_image_confirm", {"attempt": "wan-attempt.json", "quote": "quote.json", "output": "wan-confirmation.json", "user_confirmed": True, "now": NOW})
        result = tool_result(client.call("wanxiang_image_submit", {"attempt": "wan-attempt.json", "confirmation": "wan-confirmation.json", "now": NOW}))
        self.assertEqual(result["status"], "downloaded")
        self.assertEqual(result["model"], "wan2.7-image")
        self.assertTrue(load_json(self.root / "wan-confirmation.json")["consumed_at"])


if __name__ == "__main__":
    unittest.main()
