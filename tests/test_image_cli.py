from __future__ import annotations

import base64
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from tests._bootstrap import ROOT
from tests.test_image_api_providers import FakeImageTransport, png_bytes
from tests import test_sprite_cli
from tests.test_map_contract import make_map_request
from tests.test_tilemap_contract import make_tilemap_request
from game_visual_forge.contracts import SourcePreference
from game_visual_forge.cli.main import main
from game_visual_forge.contracts.serialization import dump_json, load_json


NOW = "2026-11-17T00:00:00Z"


class ImageCliTests(unittest.TestCase):
    def command(self, *args):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = main([str(item) for item in args])
        self.assertEqual(code, 0, errors.getvalue())
        return json.loads(output.getvalue())

    def test_skill_launcher_exposes_minimax_without_codex(self):
        for skill in ("forge-2d-sprite", "forge-2d-map"):
            result = subprocess.run([sys.executable, str(ROOT / "skills" / skill / "scripts/run.py"), "image", "provider", "models"], cwd=tempfile.gettempdir(), capture_output=True, text=True, encoding="utf-8", check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["models"][0]["model"], "MiniMax-H3-Image")

    def test_minimax_fixture_continues_through_sprite_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = test_sprite_cli.SpriteCliTests()
            request_path = fixture.make_request(root)
            request = load_json(request_path)
            request["source_preference"] = "auto"
            dump_json(request_path, request)
            source = fixture.make_source(root)
            transport = FakeImageTransport([{"data": [{"b64_json": base64.b64encode(source.read_bytes()).decode()}]}])
            run = root / "run"
            state, normalized, decision = run / "job-state.json", run / "sprite-request.json", run / "decision.json"
            capability, preflight = root / "capabilities.json", root / "preflight.json"
            dump_json(capability, {"schema_version": 1, "supported": False, "operations": []})
            self.command("sprite", "plan", "--request", request_path, "--out-dir", run, "--now", NOW)
            with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-secret"}):
                self.command("image", "provider", "preflight", "--out", preflight)
                selection = self.command("sprite", "route", "--request", normalized, "--capabilities", capability, "--preflight", preflight, "--out", decision, "--state", state, "--now", NOW)
                self.assertTrue(selection["requires_user_selection"])
                self.assertEqual(selection["status"], "planned")
                self.assertEqual(selection["recommended_provider"], "minimax")
                self.command("sprite", "route", "--request", normalized, "--capabilities", capability, "--selection", "minimax", "--preflight", preflight, "--out", decision, "--state", state, "--now", NOW)
                attempt, confirmation, quote, parameters = run / "image-attempt.json", run / "confirmation.json", run / "quote.json", run / "parameters.json"
                dump_json(parameters, {"size": "1024x1024"})
                prepared = self.command("image", "provider", "prepare", "--request", normalized, "--decision", decision, "--parameters", parameters, "--state", state, "--repo-root", root, "--out", attempt, "--now", NOW)
                self.assertIn("whole animation sheet", prepared["parameters"]["prompt"])
                self.assertIn("#ff00ff", prepared["parameters"]["prompt"])
                dump_json(quote, {"schema_version": 1, "provider": "minimax", "currency": "CNY", "amount": "0.20", "verified": True, "notice": "fixture only"})
                self.command("image", "provider", "confirm", "--attempt", attempt, "--quote", quote, "--out", confirmation, "--now", NOW)
                with patch("game_visual_forge.providers.minimax_image.ImageHttpTransport", return_value=transport):
                    self.command("image", "provider", "submit", "--attempt", attempt, "--confirmation", confirmation, "--repo-root", root, "--now", NOW)
                downloaded = self.command("image", "provider", "download", "--attempt", attempt, "--repo-root", root, "--now", NOW)
            raw = run / "raw-image.json"
            self.command("sprite", "ingest", "--request", normalized, "--decision", decision, "--image", root / downloaded["outputs"][0]["path"], "--image-attempt", attempt, "--repo-root", root, "--out", raw, "--state", state, "--now", NOW)
            self.assertEqual(load_json(raw)["provider"], "minimax")
            self.assertEqual(load_json(raw)["model"], "MiniMax-H3-Image")
            final = root / "outputs/hero-run"
            processed = self.command("sprite", "process", "--request", normalized, "--raw-image", raw, "--repo-root", root, "--out-dir", final, "--state", state, "--now", NOW)
            staging = root / processed["staging_dir"]
            review = run / "review.json"
            dump_json(review, {"schema_version": 1, "checks": {key: "passed" for key in ("character-identity-consistency", "action-and-direction-correctness", "equipment-continuity", "anatomy-and-silhouette", "unwanted-text-or-watermark", "semantic-duplicate-frames")}})
            result = self.command("sprite", "validate", "--request", normalized, "--raw-image", raw, "--processing-result", staging / "processing-result.json", "--repo-root", root, "--staging-dir", staging, "--final-dir", final, "--visual-review", review, "--state", state, "--now", NOW)
            self.assertEqual(result["status"], "completed")
            self.assertTrue((final / "asset-manifest.json").is_file())
            self.assertEqual(len(transport.calls), 1)

    def test_map_and_tilemap_api_downloads_preserve_provider_source(self):
        for kind, make_request in (("map", make_map_request), ("tilemap", make_tilemap_request)):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                request_path, capabilities, preflight = root / "request.json", root / "capabilities.json", root / "preflight.json"
                request = replace(make_request(), source_preference=SourcePreference.AUTO)
                dump_json(request_path, request.to_dict())
                dump_json(capabilities, {"schema_version": 1, "supported": False, "operations": []})
                prefix = ("map", "tile") if kind == "tilemap" else ("map",)
                run = root / "run"
                state, normalized, decision = run / "job-state.json", run / f"{kind}-request.json", run / "decision.json"
                self.command(*prefix, "plan", "--request", request_path, "--out-dir", run, "--now", NOW)
                attempt, confirmation, parameters, quote = run / "attempt.json", run / "confirmation.json", run / "parameters.json", run / "quote.json"
                dump_json(parameters, {"size": "1024x1024"})
                transport = FakeImageTransport([{"data": [{"b64_json": base64.b64encode(png_bytes()).decode()}]}])
                with patch.dict(os.environ, {"MINIMAX_API_KEY": "secret"}):
                    self.command("image", "provider", "preflight", "--out", preflight)
                    self.command(*prefix, "route", "--request", normalized, "--capabilities", capabilities, "--selection", "minimax", "--preflight", preflight, "--out", decision, "--state", state, "--now", NOW)
                    self.command("image", "provider", "prepare", "--kind", kind, "--request", normalized, "--decision", decision, "--parameters", parameters, "--state", state, "--repo-root", root, "--out", attempt, "--now", NOW)
                    dump_json(quote, {"schema_version": 1, "provider": "minimax", "currency": "CNY", "amount": "0.20", "verified": True, "notice": "fixture"})
                    self.command("image", "provider", "confirm", "--attempt", attempt, "--quote", quote, "--out", confirmation, "--now", NOW)
                    with patch("game_visual_forge.providers.minimax_image.ImageHttpTransport", return_value=transport):
                        self.command("image", "provider", "submit", "--attempt", attempt, "--confirmation", confirmation, "--repo-root", root, "--now", NOW)
                    result = self.command("image", "provider", "download", "--attempt", attempt, "--repo-root", root, "--now", NOW)
                raw = run / "raw-image.json"
                self.command(*prefix, "ingest", "--request", normalized, "--decision", decision, "--image", root / result["outputs"][0]["path"], "--repo-root", root, "--out", raw, "--state", state, "--now", NOW)
                self.assertEqual(load_json(raw)["source_type"], "minimax")
                self.assertEqual(load_json(raw)["provider"], "minimax")

    def test_native_fallback_retry_and_switch_back_preserve_job_state(self):
        for kind in ("sprite", "map", "tilemap"):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                request_path = root / "request.json"
                if kind == "sprite":
                    request_path = test_sprite_cli.SpriteCliTests().make_request(root)
                    request = load_json(request_path)
                    request["source_preference"] = "auto"
                else:
                    request = replace((make_map_request if kind == "map" else make_tilemap_request)(), source_preference=SourcePreference.AUTO).to_dict()
                dump_json(request_path, request)
                capabilities, preflight = root / "capabilities.json", root / "preflight.json"
                dump_json(capabilities, {"schema_version": 1, "supported": True, "operations": ["text-to-image", "reference-image"]})
                dump_json(preflight, {"schema_version": 1, "provider": "minimax", "available": True, "authenticated": True, "executable": None, "version": "1", "account_credit": None, "reason": "fixture"})
                prefix = ("map", "tile") if kind == "tilemap" else (kind,)
                run = root / "run"
                state, normalized, decision = run / "job-state.json", run / f"{kind}-request.json", run / "decision.json"
                self.command(*prefix, "plan", "--request", request_path, "--out-dir", run, "--now", NOW)
                arguments = (*prefix, "route", "--request", normalized, "--capabilities", capabilities, "--out", decision, "--state", state, "--now", NOW)
                self.assertEqual(self.command(*arguments)["source_type"], "agent-native")
                native_state = load_json(state)
                for action in ("api-fallback", "native-retry", "return-to-native", "invalid-active-state"):
                    with self.subTest(kind=kind, action=action):
                        dump_json(state, native_state)
                        if action == "api-fallback":
                            waiting = self.command(*arguments, "--native-outcome", "failed")
                            self.assertTrue(waiting["requires_user_selection"])
                            self.assertEqual(waiting["status"], "ready")
                            selected = self.command(*arguments, "--native-outcome", "failed", "--selection", "minimax", "--preflight", preflight)
                            self.assertEqual(selected["status"], "awaiting_confirmation")
                        elif action == "native-retry":
                            self.assertEqual(self.command(*arguments, "--selection", "agent-native")["status"], "ready")
                        elif action == "return-to-native":
                            dump_json(state, {**native_state, "status": "awaiting_confirmation", "provider": "minimax"})
                            self.assertEqual(self.command(*arguments, "--selection", "agent-native")["status"], "ready")
                            self.assertIsNone(load_json(state)["provider"])
                            self.assertIsNone(load_json(state)["ready_provenance"])
                        else:
                            dump_json(state, {**native_state, "status": "running"})
                            previous = load_json(decision)
                            output, errors = io.StringIO(), io.StringIO()
                            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                                code = main([str(value) for value in (*arguments, "--selection", "minimax", "--preflight", preflight)])
                            self.assertEqual(code, 1)
                            self.assertEqual(load_json(decision), previous)


if __name__ == "__main__":
    unittest.main()
