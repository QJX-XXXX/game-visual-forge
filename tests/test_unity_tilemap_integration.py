from __future__ import annotations

import json
import unittest

from tests._bootstrap import ROOT


class UnityTilemapIntegrationTests(unittest.TestCase):
    def test_package_declares_supported_unity_and_dependencies(self) -> None:
        package_root = ROOT / "integrations" / "unity" / "com.game-visual-forge.tilemap"
        payload = json.loads((package_root / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["name"], "com.game-visual-forge.tilemap")
        self.assertEqual(payload["unity"], "2022.3")
        self.assertEqual(set(payload["dependencies"]), {"com.unity.2d.sprite", "com.unity.2d.tilemap"})

    def test_importer_uses_supported_sprite_provider_and_does_not_modify_scenes(self) -> None:
        source = (ROOT / "integrations" / "unity" / "com.game-visual-forge.tilemap" / "Editor" / "TilemapBundleImporter.cs").read_text(encoding="utf-8")
        self.assertIn("SpriteDataProviderFactories", source)
        self.assertIn("SetSpriteRects", source)
        self.assertIn("ISpriteNameFileIdDataProvider", source)
        self.assertNotIn("TextureImporter.spritesheet", source)
        self.assertIn("PrefabUtility.SaveAsPrefabAsset", source)
        self.assertIn("tilesets", source)
        self.assertIn("atlas_id", source)
        self.assertIn("ImportMode.AssetsOnly", source)

    def test_optional_unity_runtime_checks_are_packaged(self) -> None:
        package_root = ROOT / "integrations" / "unity" / "com.game-visual-forge.tilemap"
        editor_tests = package_root / "Tests" / "Editor" / "TilemapBundleImporterEditModeTests.cs"
        playmode_tests = package_root / "Tests" / "PlayMode" / "TilemapPrefabPlayModeTests.cs"
        self.assertTrue(editor_tests.is_file())
        self.assertTrue(playmode_tests.is_file())
        self.assertIn("TilemapCollider2D", editor_tests.read_text(encoding="utf-8"))
        self.assertIn("TilemapRenderer", playmode_tests.read_text(encoding="utf-8"))

    def test_multi_page_import_and_report_sources_are_packaged(self) -> None:
        package_root = ROOT / "integrations" / "unity" / "com.game-visual-forge.tilemap"
        contracts = (package_root / "Editor" / "TilemapBundleContracts.cs").read_text(encoding="utf-8")
        placer = (package_root / "Editor" / "TilemapScenePlacer.cs").read_text(encoding="utf-8")
        writer = (package_root / "Editor" / "TilemapImportReportWriter.cs").read_text(encoding="utf-8")
        self.assertIn("AssetsOnly", contracts)
        self.assertIn("ImportAndPlace", contracts)
        self.assertIn("PlaceOrUpdate", placer)
        self.assertIn("quality_report_sha256", writer)


if __name__ == "__main__":
    unittest.main()
