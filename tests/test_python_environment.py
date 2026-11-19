from __future__ import annotations

import contextlib
import ast
import io
import json
import runpy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests._bootstrap import ROOT


CHECKER = ROOT / "install/check_environment.py"


class PythonEnvironmentTests(unittest.TestCase):
    def make_repository(self, root):
        (root / "skills").mkdir()
        (root / "src/game_visual_forge").mkdir(parents=True)
        (root / "pyproject.toml").write_text("[project]\nname='game-visual-forge'\n", encoding="utf-8")

    def inspect(self, root, **options):
        return runpy.run_path(str(CHECKER))["inspect_environment"](root, **options)

    def test_core_checker_runs_outside_repository_without_importing_forge(self):
        result = subprocess.run([sys.executable, str(CHECKER), "--profile", "core"], cwd=tempfile.gettempdir(), capture_output=True, text=True, encoding="utf-8", check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["status"], "ready")
        self.assertEqual(Path(report["python"]["executable"]), Path(sys.executable))
        self.assertEqual(Path(report["repo_root"]), ROOT)

    def test_checker_syntax_is_compatible_with_python_38(self):
        ast.parse(CHECKER.read_text(encoding="utf-8"), feature_version=(3, 8))

    def test_old_python_reports_upgrade_before_dependency_imports(self):
        def unexpected_probe(name):
            self.fail("old Python should not probe runtime dependencies")
        report = self.inspect(ROOT, version=(3, 10, 0), probe=unexpected_probe)
        self.assertEqual(report["status"], "needs_setup")
        self.assertEqual(report["missing"], ["Python >=3.11"])
        self.assertEqual(report["suggested_commands"], [])
        self.assertIn("python.org", report["guidance"])

    def test_image_profile_does_not_require_or_import_rembg(self):
        probes = []
        def available(name):
            probes.append(name)
            return True
        report = self.inspect(ROOT, profile="image", probe=available)
        self.assertEqual(report["status"], "ready")
        self.assertNotIn("rembg", probes)
        self.assertEqual(report["suggested_commands"], [])
        background = self.inspect(ROOT, profile="background", probe=lambda name: name != "rembg")
        self.assertEqual(background["missing"], ["rembg"])
        self.assertEqual(background["status"], "needs_setup")

    def test_missing_packages_produce_platform_specific_isolated_commands(self):
        with tempfile.TemporaryDirectory(prefix="forge space ") as directory:
            root = Path(directory)
            self.make_repository(root)
            for system, suffix in (("Windows", "Scripts/python.exe"), ("Linux", "bin/python"), ("Darwin", "bin/python")):
                with self.subTest(system=system):
                    report = self.inspect(root, profile="image", system=system, virtual_environment=False, probe=lambda name: name != "PIL.Image")
                    commands = report["suggested_commands"]
                    self.assertEqual(report["missing"], ["Pillow"])
                    self.assertEqual(commands[0]["argv"], [sys.executable, "-m", "venv", str(root / ".venv")])
                    target = str(root / ".venv" / suffix)
                    self.assertEqual(commands[-1]["argv"], [target, "-m", "pip", "install", "-e", str(root) + "[image]"])
                    self.assertFalse((root / ".venv").exists())

    def test_image_profile_requires_numpy(self):
        report = self.inspect(ROOT, profile="image", probe=lambda name: name != "numpy")
        self.assertEqual(report["status"], "needs_setup")
        self.assertEqual(report["missing"], ["numpy"])

    def test_background_profile_suggests_the_selected_onnx_backend(self):
        for backend in ("cpu", "gpu"):
            with self.subTest(backend=backend):
                report = self.inspect(
                    ROOT, profile="background", virtual_environment=True,
                    probe=lambda name: name != "onnxruntime", onnx_runtime=backend,
                )
                self.assertIn("ONNX Runtime", report["missing"])
                self.assertIn(f"rembg[{backend}]", report["suggested_commands"][-1]["argv"])

    def test_current_venv_installs_only_selected_extra_without_creating_another(self):
        report = self.inspect(ROOT, profile="image", virtual_environment=True, probe=lambda name: name != "PIL.Image")
        self.assertEqual(report["suggested_commands"], [{"action": "install-selected-extra", "argv": [sys.executable, "-m", "pip", "install", "-e", str(ROOT) + "[image]"]}])

    def test_explicit_destination_is_respected_even_inside_another_venv(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "chosen-env"
            report = self.inspect(ROOT, profile="image", virtual_environment=True, venv_dir=target, probe=lambda name: name != "PIL.Image")
            self.assertEqual(report["suggested_commands"][0]["argv"], [sys.executable, "-m", "venv", str(target)])
            self.assertIn(str(target), report["suggested_commands"][-1]["argv"][0])

    def test_existing_environment_is_rechecked_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repository(root)
            python = root / ".venv/Scripts/python.exe"
            python.parent.mkdir(parents=True)
            python.write_bytes(b"sentinel")
            report = self.inspect(root, system="Windows", virtual_environment=False, probe=lambda name: name != "PIL.Image")
            self.assertEqual(report["suggested_commands"][0]["action"], "recheck-existing-environment")
            self.assertEqual(report["suggested_commands"][0]["argv"][0], str(python))
            self.assertEqual(python.read_bytes(), b"sentinel")

    def test_existing_non_environment_directory_requires_another_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repository(root)
            target = root / ".venv"
            target.mkdir()
            report = self.inspect(root, virtual_environment=False, probe=lambda name: name != "PIL.Image")
            self.assertEqual(report["suggested_commands"], [])
            self.assertIn("choose another", report["guidance"])
            self.assertEqual(list(target.iterdir()), [])

    def test_wrong_repository_does_not_offer_package_installation(self):
        with tempfile.TemporaryDirectory() as directory:
            report = self.inspect(Path(directory), probe=lambda name: False)
            self.assertEqual(report["status"], "needs_setup")
            self.assertEqual(report["missing"], ["Forge repository"])
            self.assertEqual(report["suggested_commands"], [])

    def test_all_skill_launchers_explain_old_python_before_runtime_import(self):
        for skill in ("forge-2d-sprite", "forge-2d-map", "forge-video-to-sprite", "forge-text-audio", "forge-game-music"):
            with self.subTest(skill=skill):
                errors = io.StringIO()
                with patch.object(sys, "version_info", (3, 10, 0)), contextlib.redirect_stderr(errors), self.assertRaises(SystemExit) as stopped:
                    runpy.run_path(str(ROOT / "skills" / skill / "scripts/run.py"), run_name="__main__")
                self.assertEqual(stopped.exception.code, 1)
                self.assertEqual(json.loads(errors.getvalue())["missing"], ["Python >=3.11"])


if __name__ == "__main__":
    unittest.main()
