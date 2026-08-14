from __future__ import annotations

import json
import unittest
from pathlib import Path

from tests._bootstrap import ROOT  # noqa: F401


PACKAGE = ROOT / "integrations" / "unity" / "com.game-visual-forge.audio"


class UnityAudioIntegrationTests(unittest.TestCase):
    def test_audio_package_identity_and_required_files(self) -> None:
        package = json.loads((PACKAGE / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["name"], "com.game-visual-forge.audio")
        for relative in (
            "package.json.meta",
            "Editor.meta",
            "Editor/GameVisualForge.Audio.Editor.asmdef",
            "Editor/GameVisualForge.Audio.Editor.asmdef.meta",
            "Editor/AudioBundleContracts.cs",
            "Editor/AudioBundleImporter.cs",
            "Editor/AudioImportReportWriter.cs",
            "Tests.meta",
            "Tests/Editor.meta",
            "Tests/Editor/GameVisualForge.Audio.Tests.Editor.asmdef",
            "Tests/Editor/AudioBundleImporterEditModeTests.cs",
        ):
            self.assertTrue((PACKAGE / relative).is_file(), relative)

    def test_audio_package_is_assets_only(self) -> None:
        importer = (PACKAGE / "Editor" / "AudioBundleImporter.cs").read_text(encoding="utf-8")
        self.assertIn("ImportBundleForAutomation", importer)
        self.assertIn("AudioImporter", importer)
        self.assertIn("ComputeSHA256", importer)
        self.assertNotIn("AudioSource", importer)
        self.assertNotIn("ImportAndPlace", importer)

    def test_report_contains_runtime_audio_fields(self) -> None:
        contracts = (PACKAGE / "Editor" / "AudioBundleContracts.cs").read_text(encoding="utf-8")
        for fragment in ("frequency", "channels", "duration", "guid_stable", "scene_action"):
            self.assertIn(fragment, contracts)


if __name__ == "__main__":
    unittest.main()
