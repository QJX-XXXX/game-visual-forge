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
        self.assertNotIn("EditorSceneManager", source)
        self.assertIn("PrefabUtility.SaveAsPrefabAsset", source)


if __name__ == "__main__":
    unittest.main()
