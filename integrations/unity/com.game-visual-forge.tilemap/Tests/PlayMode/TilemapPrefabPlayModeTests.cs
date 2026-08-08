using System;
using System.Collections;
using System.IO;
using System.Linq;
using System.Reflection;
using NUnit.Framework;
using UnityEditor;
using UnityEngine;
using UnityEngine.TestTools;
using UnityEngine.Tilemaps;
using Object = UnityEngine.Object;

namespace GameVisualForge.Unity.Tests
{
    public sealed class TilemapPrefabPlayModeTests
    {
        private const string TilemapPrefabPath = "Assets/GameVisualForgeMaps/autumn-creek-map/Prefabs/autumn-creek-map-tilemap.prefab";
        private const string RectangularFixtureRoot = "Assets/GameVisualForgeTask3PlayModeFixture";
        private const string RectangularGeneratedRoot = RectangularFixtureRoot + "/Generated";
        private const string RectangularPrefabPath = RectangularGeneratedRoot + "/Prefabs/task-3-rectangular-tilemap.prefab";

        [UnityTest]
        public IEnumerator ImportedTilemapRemainsRenderableAtRuntime()
        {
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(TilemapPrefabPath);
            if (prefab == null)
                Assert.Ignore("Unity demo fixture is not imported: " + TilemapPrefabPath);

            var root = Object.Instantiate(prefab);
            Assert.That(root, Is.Not.Null);

            try
            {
                var tilemaps = root.GetComponentsInChildren<Tilemap>(true);

                Assert.That(tilemaps, Has.Length.EqualTo(3));
                Assert.That(tilemaps, Has.All.Matches<Tilemap>(tilemap => tilemap.GetUsedTilesCount() > 0));
                Assert.That(root.GetComponentsInChildren<TilemapRenderer>(true), Has.Length.EqualTo(3));
                Assert.That(root.GetComponentInChildren<TilemapCollider2D>(true), Is.Not.Null);

                yield return null;
            }
            finally
            {
                Object.Destroy(root);
            }
        }

        [UnityTest]
        public IEnumerator RectangularGridUsesDeclaredWorldCellHeightAtRuntime()
        {
            CreateRectangularFixture();
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(RectangularPrefabPath);
            Assert.That(prefab, Is.Not.Null);

            var root = Object.Instantiate(prefab);
            try
            {
                var grid = root.GetComponent<Grid>();
                Assert.That(grid, Is.Not.Null);
                Assert.That(grid.CellToWorld(Vector3Int.up).y - grid.CellToWorld(Vector3Int.zero).y, Is.EqualTo(1.125f));
                yield return null;
            }
            finally
            {
                Object.Destroy(root);
                AssetDatabase.DeleteAsset(RectangularFixtureRoot);
                AssetDatabase.Refresh();
            }
        }

        private static void CreateRectangularFixture()
        {
            AssetDatabase.DeleteAsset(RectangularFixtureRoot);
            var projectRoot = Directory.GetParent(Application.dataPath)?.FullName;
            Assert.That(projectRoot, Is.Not.Null);
            var bundlePath = Path.Combine(projectRoot, RectangularFixtureRoot.Replace('/', Path.DirectorySeparatorChar), "Bundle");
            Directory.CreateDirectory(bundlePath);

            var texture = new Texture2D(16, 18, TextureFormat.RGBA32, false);
            try
            {
                for (var y = 0; y < texture.height; y++)
                {
                    for (var x = 0; x < texture.width; x++)
                        texture.SetPixel(x, y, Color.white);
                }
                texture.Apply();
                File.WriteAllBytes(Path.Combine(bundlePath, "tileset.png"), texture.EncodeToPNG());
            }
            finally
            {
                Object.DestroyImmediate(texture);
            }

            File.WriteAllText(Path.Combine(bundlePath, "slices.json"), @"{
  ""schema_version"": 1,
  ""tiles"": [ { ""id"": ""tile-00"", ""rect"": { ""x"": 0, ""y"": 0, ""width"": 16, ""height"": 18 }, ""palette"": { ""x"": 0, ""y"": 0 }, ""collider_type"": ""none"" } ]
}");
            File.WriteAllText(Path.Combine(bundlePath, "placement.json"), @"{
  ""schema_version"": 1,
  ""map_size"": { ""width"": 1, ""height"": 1 },
  ""layers"": [ { ""id"": ""ground"", ""sorting_order"": 0, ""has_collider"": false, ""placements"": [ { ""x"": 0, ""y"": 0, ""tile_id"": ""tile-00"" } ] } ]
}");
            var manifestPath = Path.Combine(bundlePath, "manifest.json");
            File.WriteAllText(manifestPath, @"{
  ""schema_version"": 1,
  ""asset_id"": ""task-3-rectangular-playmode-fixture"",
  ""engine_target"": ""Unity_Tilemap"",
  ""tileset"": ""tileset.png"",
  ""slices"": ""slices.json"",
  ""placement"": ""placement.json"",
  ""generated_root"": """ + RectangularGeneratedRoot + @""",
  ""pixels_per_unit"": 16,
  ""tile_width"": 16,
  ""tile_height"": 18,
  ""filter_mode"": ""point"",
  ""palette_name"": ""Task 3 Rectangular Palette"",
  ""prefab_name"": ""task-3-rectangular-tilemap""
}");

            AssetDatabase.Refresh();
            var importerType = AppDomain.CurrentDomain.GetAssemblies()
                .Select(assembly => assembly.GetType("GameVisualForge.Unity.TilemapBundleImporter"))
                .FirstOrDefault(type => type != null);
            Assert.That(importerType, Is.Not.Null, "Tilemap importer assembly is not loaded.");
            var importBundle = importerType.GetMethod("ImportBundle", BindingFlags.Public | BindingFlags.Static, null, new[] { typeof(string) }, null);
            Assert.That(importBundle, Is.Not.Null, "Tilemap importer method is not available.");
            importBundle.Invoke(null, new object[] { manifestPath });
        }
    }
}
