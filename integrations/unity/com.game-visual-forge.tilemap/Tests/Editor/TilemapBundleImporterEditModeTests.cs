using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using GameVisualForge.Unity;
using NUnit.Framework;
using UnityEditor;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.Tilemaps;

namespace GameVisualForge.Unity.Tests
{
    public sealed class TilemapBundleImporterEditModeTests
    {
        private const string MapRoot = "Assets/GameVisualForgeMaps/autumn-creek-map";
        private const string TileRoot = MapRoot + "/Tiles";
        private const string TilemapPrefabPath = MapRoot + "/Prefabs/autumn-creek-map-tilemap.prefab";
        private const string PalettePrefabPath = MapRoot + "/Palettes/Autumn Creek Map Palette.prefab";
        private const string TestGeneratedRoot = "Assets/GameVisualForgeTask6ImportFixtures";
        private const string MultiPageGeneratedRoot = TestGeneratedRoot + "/MultiPage";
        private const string LegacyGeneratedRoot = TestGeneratedRoot + "/LegacySinglePage";
        private const string Task7BundleRoot = TestGeneratedRoot + "/Task7Bundle";
        private const string Task7GeneratedRoot = TestGeneratedRoot + "/Task7Generated";
        private const string Task7PrefabPath = Task7GeneratedRoot + "/Prefabs/task-7-placement-report-tilemap.prefab";
        private const string Task7ReportPath = Task7GeneratedRoot + "/Reports/unity-import-report.json";

        [SetUp]
        public void SetUp()
        {
            RemoveTask7SceneInstances();
            DeleteAssetIfExists(TestGeneratedRoot);
        }

        [TearDown]
        public void TearDown()
        {
            RemoveTask7SceneInstances();
            DeleteAssetIfExists(TestGeneratedRoot);
        }

        [OneTimeTearDown]
        public void OneTimeTearDown()
        {
            AssetDatabase.DeleteAsset(TestGeneratedRoot);
        }

        [Test]
        public void AutumnCreekTileSetContainsAllManifestTiles()
        {
            RequireFixture(TileRoot);

            var tileGuids = AssetDatabase.FindAssets("t:Tile", new[] { TileRoot });

            Assert.That(tileGuids.Length, Is.EqualTo(16));
            Assert.That(AssetDatabase.LoadAssetAtPath<Tile>(TileRoot + "/tree-canopy.asset"), Is.Not.Null);
        }

        [Test]
        public void AutumnCreekPrefabContainsOrderedLayersAndObstacleCollider()
        {
            var prefab = LoadFixture<GameObject>(TilemapPrefabPath);
            var tilemaps = prefab.GetComponentsInChildren<Tilemap>(true);
            var byName = tilemaps.ToDictionary(tilemap => tilemap.name);

            Assert.That(tilemaps, Has.Length.EqualTo(3));
            Assert.That(byName.Keys, Is.EquivalentTo(new[] { "ground", "details", "obstacles" }));
            Assert.That(byName["ground"].GetUsedTilesCount(), Is.GreaterThan(0));
            Assert.That(byName["details"].GetUsedTilesCount(), Is.GreaterThan(0));
            Assert.That(byName["obstacles"].GetUsedTilesCount(), Is.GreaterThan(0));
            Assert.That(byName["obstacles"].GetComponent<TilemapCollider2D>(), Is.Not.Null);
            Assert.That(byName["ground"].GetComponent<TilemapRenderer>().sortingOrder, Is.EqualTo(0));
            Assert.That(byName["details"].GetComponent<TilemapRenderer>().sortingOrder, Is.EqualTo(1));
            Assert.That(byName["obstacles"].GetComponent<TilemapRenderer>().sortingOrder, Is.EqualTo(2));
        }

        [Test]
        public void AutumnCreekPaletteContainsAllTiles()
        {
            var palette = LoadFixture<GameObject>(PalettePrefabPath);
            var paletteTilemap = palette.GetComponentInChildren<Tilemap>(true);

            Assert.That(paletteTilemap, Is.Not.Null);
            Assert.That(paletteTilemap.GetUsedTilesCount(), Is.EqualTo(16));
        }

        [Test]
        public void ImportBundleCombinesTwoAtlasPagesIntoOnePalette()
        {
            var manifestPath = CreateTwoPageBundleFixture();

            var result = TilemapBundleImporter.ImportBundle(manifestPath);

            Assert.That(result.tileset_assets, Has.Length.EqualTo(2));
            Assert.That(result.tile_count, Is.EqualTo(32));
            Assert.That(AssetDatabase.FindAssets("t:Tile", new[] { result.generated_root + "/Tiles" }), Has.Length.EqualTo(32));
            var palette = AssetDatabase.LoadAssetAtPath<GameObject>(result.palette_prefab);
            Assert.That(palette.GetComponentInChildren<Tilemap>(true).GetUsedTilesCount(), Is.EqualTo(32));
        }

        [Test]
        public void ImportBundleTreatsLegacySlicesWithoutAtlasIdAsPageOne()
        {
            var manifestPath = CreateLegacySinglePageBundleFixture();

            var result = TilemapBundleImporter.ImportBundle(manifestPath);

            Assert.That(result.tileset_assets, Has.Length.EqualTo(1));
            Assert.That(result.tile_count, Is.EqualTo(16));
            Assert.That(AssetDatabase.FindAssets("t:Tile", new[] { result.generated_root + "/Tiles" }), Has.Length.EqualTo(16));
            var palette = AssetDatabase.LoadAssetAtPath<GameObject>(result.palette_prefab);
            Assert.That(palette.GetComponentInChildren<Tilemap>(true).GetUsedTilesCount(), Is.EqualTo(16));
        }

        [Test]
        public void AssetsOnlyImportDoesNotChangeActiveSceneRootsAndWritesReport()
        {
            var manifestPath = CreateTask7BundleFixture();
            var before = SceneManager.GetActiveScene().GetRootGameObjects().Select(item => item.GetInstanceID()).ToArray();

            var result = TilemapBundleImporter.ImportBundle(manifestPath, ImportMode.AssetsOnly);

            var after = SceneManager.GetActiveScene().GetRootGameObjects().Select(item => item.GetInstanceID()).ToArray();
            Assert.That(after, Is.EqualTo(before));
            Assert.That(result.scene_action, Is.EqualTo("unchanged"));
            Assert.That(result.scene_dirty, Is.False);
            Assert.That(result.unity_import_report, Is.EqualTo(Task7ReportPath));

            var report = ReadTask7UnityReport();
            Assert.That(report.python_quality_report, Is.EqualTo("quality-report.json"));
            Assert.That(report.python_quality_report_sha256, Is.EqualTo(ComputeSha256(Path.Combine(ToFullPath(Task7BundleRoot), "quality-report.json"))));
            Assert.That(report.atlas_page_count, Is.EqualTo(2));
            Assert.That(report.atlas_page_paths, Is.EqualTo(result.tileset_assets));
            Assert.That(report.tile_count, Is.EqualTo(32));
            Assert.That(report.tile_paths, Is.EqualTo(result.tile_assets));
            Assert.That(report.palette_path, Is.EqualTo(result.palette_prefab));
            Assert.That(report.prefab_path, Is.EqualTo(result.tilemap_prefab));
            Assert.That(report.scene_action, Is.EqualTo("unchanged"));
            Assert.That(report.had_existing_assets, Is.False);
            Assert.That(report.resource_guids_stable, Is.True);
        }

        [Test]
        public void ImportAndPlaceReusesExistingPrefabInstanceAndReportsStableExistingAssets()
        {
            var manifestPath = CreateTask7BundleFixture();

            var first = TilemapBundleImporter.ImportBundle(manifestPath, ImportMode.ImportAndPlace);
            var firstGuids = CaptureGuids(new[] { first.tileset_assets[0], first.tile_assets[0], first.palette_prefab, first.tilemap_prefab });
            var firstReport = ReadTask7UnityReport();
            var second = TilemapBundleImporter.ImportBundle(manifestPath, ImportMode.ImportAndPlace);
            var secondReport = ReadTask7UnityReport();
            var matches = SceneManager.GetActiveScene().GetRootGameObjects()
                .Count(root => PrefabUtility.GetPrefabAssetPathOfNearestInstanceRoot(root) == second.tilemap_prefab);

            Assert.That(first.scene_action, Is.EqualTo("placed"));
            Assert.That(firstReport.scene_action, Is.EqualTo("placed"));
            Assert.That(firstReport.had_existing_assets, Is.False);
            Assert.That(matches, Is.EqualTo(1));
            Assert.That(second.scene_action, Is.EqualTo("updated"));
            Assert.That(second.scene_dirty, Is.True);
            Assert.That(secondReport.scene_action, Is.EqualTo("updated"));
            Assert.That(secondReport.had_existing_assets, Is.True);
            Assert.That(secondReport.resource_guids_stable, Is.True);
            foreach (var item in firstGuids)
                Assert.That(AssetDatabase.AssetPathToGUID(item.Key), Is.EqualTo(item.Value), item.Key);
        }

        private static string CreateTwoPageBundleFixture()
        {
            var bundleAssetPath = TestGeneratedRoot + "/MultiPageBundle";
            var bundleFullPath = ToFullPath(bundleAssetPath);
            Directory.CreateDirectory(bundleFullPath);

            WriteAtlasPage(Path.Combine(bundleFullPath, "page-01.png"), 0);
            WriteAtlasPage(Path.Combine(bundleFullPath, "page-02.png"), 16);
            File.WriteAllText(Path.Combine(bundleFullPath, "slices.json"), BuildSlicesJson());
            File.WriteAllText(Path.Combine(bundleFullPath, "placement.json"), BuildPlacementJson());

            var manifestPath = Path.Combine(bundleFullPath, "manifest.json");
            File.WriteAllText(
                manifestPath,
                @"{
  ""schema_version"": 1,
  ""asset_id"": ""task-6-multi-page-fixture"",
  ""engine_target"": ""Unity_Tilemap"",
  ""tilesets"": [
    { ""atlas_id"": ""page-01"", ""path"": ""page-01.png"" },
    { ""atlas_id"": ""page-02"", ""path"": ""page-02.png"" }
  ],
  ""slices"": ""slices.json"",
  ""placement"": ""placement.json"",
  ""generated_root"": """ + MultiPageGeneratedRoot + @""",
  ""pixels_per_unit"": 1,
  ""filter_mode"": ""point"",
  ""palette_name"": ""Task 6 Multi Page Palette"",
  ""prefab_name"": ""task-6-multi-page-tilemap""
}");

            AssetDatabase.Refresh();
            return manifestPath;
        }

        private static string CreateTask7BundleFixture()
        {
            var bundleFullPath = ToFullPath(Task7BundleRoot);
            Directory.CreateDirectory(bundleFullPath);

            WriteAtlasPage(Path.Combine(bundleFullPath, "page-01.png"), 0);
            WriteAtlasPage(Path.Combine(bundleFullPath, "page-02.png"), 16);
            File.WriteAllText(Path.Combine(bundleFullPath, "slices.json"), BuildSlicesJson());
            File.WriteAllText(Path.Combine(bundleFullPath, "placement.json"), BuildPlacementJson());
            File.WriteAllText(Path.Combine(bundleFullPath, "quality-report.json"), "{\n  \"status\": \"pass\",\n  \"tile_count\": 32\n}\n");
            var qualityReportHash = ComputeSha256(Path.Combine(bundleFullPath, "quality-report.json"));

            var manifestPath = Path.Combine(bundleFullPath, "manifest.json");
            File.WriteAllText(
                manifestPath,
                @"{
  ""schema_version"": 1,
  ""asset_id"": ""task-7-placement-report-fixture"",
  ""engine_target"": ""Unity_Tilemap"",
  ""tilesets"": [
    { ""atlas_id"": ""page-01"", ""path"": ""page-01.png"" },
    { ""atlas_id"": ""page-02"", ""path"": ""page-02.png"" }
  ],
  ""slices"": ""slices.json"",
  ""placement"": ""placement.json"",
  ""quality_report"": ""quality-report.json"",
  ""quality_report_sha256"": """ + qualityReportHash + @""",
  ""generated_root"": """ + Task7GeneratedRoot + @""",
  ""pixels_per_unit"": 1,
  ""filter_mode"": ""point"",
  ""palette_name"": ""Task 7 Placement Report Palette"",
  ""prefab_name"": ""task-7-placement-report-tilemap""
}");

            AssetDatabase.Refresh();
            return manifestPath;
        }

        private static string CreateLegacySinglePageBundleFixture()
        {
            var bundleAssetPath = TestGeneratedRoot + "/LegacyBundle";
            var bundleFullPath = ToFullPath(bundleAssetPath);
            Directory.CreateDirectory(bundleFullPath);

            WriteAtlasPage(Path.Combine(bundleFullPath, "tileset.png"), 0);
            File.WriteAllText(Path.Combine(bundleFullPath, "slices.json"), BuildLegacySlicesJson());
            File.WriteAllText(Path.Combine(bundleFullPath, "placement.json"), BuildLegacyPlacementJson());

            var manifestPath = Path.Combine(bundleFullPath, "manifest.json");
            File.WriteAllText(
                manifestPath,
                @"{
  ""schema_version"": 1,
  ""asset_id"": ""task-6-legacy-single-page-fixture"",
  ""engine_target"": ""Unity_Tilemap"",
  ""tileset"": ""tileset.png"",
  ""slices"": ""slices.json"",
  ""placement"": ""placement.json"",
  ""generated_root"": """ + LegacyGeneratedRoot + @""",
  ""pixels_per_unit"": 1,
  ""filter_mode"": ""point"",
  ""palette_name"": ""Task 6 Legacy Palette"",
  ""prefab_name"": ""task-6-legacy-tilemap""
}");

            AssetDatabase.Refresh();
            return manifestPath;
        }

        private static void WriteAtlasPage(string path, int colorOffset)
        {
            var texture = new Texture2D(4, 4, TextureFormat.RGBA32, false);
            try
            {
                for (var y = 0; y < 4; y++)
                {
                    for (var x = 0; x < 4; x++)
                    {
                        var value = colorOffset + y * 4 + x;
                        texture.SetPixel(x, y, new Color32((byte)(32 + value * 5), (byte)(64 + value * 3), (byte)(128 + value * 2), 255));
                    }
                }

                texture.Apply();
                File.WriteAllBytes(path, texture.EncodeToPNG());
            }
            finally
            {
                Object.DestroyImmediate(texture);
            }
        }

        private static string BuildSlicesJson()
        {
            var items = new List<string>();
            for (var pageIndex = 0; pageIndex < 2; pageIndex++)
            {
                var atlasId = pageIndex == 0 ? "page-01" : "page-02";
                for (var tileIndex = 0; tileIndex < 16; tileIndex++)
                {
                    var globalIndex = pageIndex * 16 + tileIndex;
                    items.Add(
                        "    { " +
                        $@"""id"": ""{TileId(globalIndex)}"", " +
                        $@"""atlas_id"": ""{atlasId}"", " +
                        $@"""rect"": {{ ""x"": {tileIndex % 4}, ""y"": {tileIndex / 4}, ""width"": 1, ""height"": 1 }}, " +
                        $@"""palette"": {{ ""x"": {globalIndex}, ""y"": 0 }}, " +
                        @"""collider_type"": ""none"" }");
                }
            }

            return "{\n  \"schema_version\": 1,\n  \"tiles\": [\n" + string.Join(",\n", items) + "\n  ]\n}";
        }

        private static string BuildLegacySlicesJson()
        {
            var items = new List<string>();
            for (var tileIndex = 0; tileIndex < 16; tileIndex++)
            {
                items.Add(
                    "    { " +
                    $@"""id"": ""{TileId(tileIndex)}"", " +
                    $@"""rect"": {{ ""x"": {tileIndex % 4}, ""y"": {tileIndex / 4}, ""width"": 1, ""height"": 1 }}, " +
                    $@"""palette"": {{ ""x"": {tileIndex}, ""y"": 0 }}, " +
                    @"""collider_type"": ""none"" }");
            }

            return "{\n  \"schema_version\": 1,\n  \"tiles\": [\n" + string.Join(",\n", items) + "\n  ]\n}";
        }

        private static string BuildPlacementJson()
        {
            var layerOne = new StringBuilder();
            var layerTwo = new StringBuilder();
            for (var tileIndex = 0; tileIndex < 16; tileIndex++)
            {
                if (tileIndex > 0)
                {
                    layerOne.Append(",\n");
                    layerTwo.Append(",\n");
                }

                layerOne.Append($"        {{ \"x\": {tileIndex}, \"y\": 0, \"tile_id\": \"{TileId(tileIndex)}\" }}");
                layerTwo.Append($"        {{ \"x\": {tileIndex}, \"y\": 1, \"tile_id\": \"{TileId(tileIndex + 16)}\" }}");
            }

            return @"{
  ""schema_version"": 1,
  ""map_size"": { ""width"": 16, ""height"": 2 },
  ""layers"": [
    {
      ""id"": ""lower"",
      ""sorting_order"": 0,
      ""has_collider"": false,
      ""placements"": [
" + layerOne + @"
      ]
    },
    {
      ""id"": ""upper"",
      ""sorting_order"": 1,
      ""has_collider"": false,
      ""placements"": [
" + layerTwo + @"
      ]
    }
  ]
}";
        }

        private static string BuildLegacyPlacementJson()
        {
            var placements = new StringBuilder();
            for (var tileIndex = 0; tileIndex < 16; tileIndex++)
            {
                if (tileIndex > 0)
                    placements.Append(",\n");

                placements.Append($"        {{ \"x\": {tileIndex}, \"y\": 0, \"tile_id\": \"{TileId(tileIndex)}\" }}");
            }

            return @"{
  ""schema_version"": 1,
  ""map_size"": { ""width"": 16, ""height"": 1 },
  ""layers"": [
    {
      ""id"": ""legacy"",
      ""sorting_order"": 0,
      ""has_collider"": false,
      ""placements"": [
" + placements + @"
      ]
    }
  ]
}";
        }

        private static string TileId(int globalIndex)
        {
            return $"tile-{globalIndex:00}";
        }

        private static string ToFullPath(string assetPath)
        {
            var projectRoot = Directory.GetParent(Application.dataPath)?.FullName;
            Assert.That(projectRoot, Is.Not.Null, "Could not resolve the Unity project root.");
            return Path.Combine(projectRoot, assetPath.Replace('/', Path.DirectorySeparatorChar));
        }

        private static UnityImportReport ReadTask7UnityReport()
        {
            var report = AssetDatabase.LoadAssetAtPath<TextAsset>(Task7ReportPath);
            Assert.That(report, Is.Not.Null, "Expected Unity import report: " + Task7ReportPath);
            return JsonUtility.FromJson<UnityImportReport>(report.text);
        }

        private static Dictionary<string, string> CaptureGuids(IEnumerable<string> assetPaths)
        {
            return assetPaths.ToDictionary(path => path, AssetDatabase.AssetPathToGUID, System.StringComparer.Ordinal);
        }

        private static string ComputeSha256(string path)
        {
            using (var stream = File.OpenRead(path))
            using (var algorithm = SHA256.Create())
                return string.Concat(algorithm.ComputeHash(stream).Select(value => value.ToString("x2")));
        }

        private static void RemoveTask7SceneInstances()
        {
            foreach (var root in SceneManager.GetActiveScene().GetRootGameObjects().ToArray())
            {
                if (PrefabUtility.GetPrefabAssetPathOfNearestInstanceRoot(root) == Task7PrefabPath)
                    Object.DestroyImmediate(root);
            }
        }

        private static void DeleteAssetIfExists(string assetPath)
        {
            if (AssetDatabase.IsValidFolder(assetPath) || AssetDatabase.LoadAssetAtPath<Object>(assetPath) != null)
                AssetDatabase.DeleteAsset(assetPath);
            var fullPath = ToFullPath(assetPath);
            if (Directory.Exists(fullPath))
                Directory.Delete(fullPath, true);
            var metaPath = fullPath + ".meta";
            if (File.Exists(metaPath))
                File.Delete(metaPath);
            AssetDatabase.Refresh();
        }

        private static T LoadFixture<T>(string assetPath) where T : Object
        {
            RequireFixture(assetPath);
            var asset = AssetDatabase.LoadAssetAtPath<T>(assetPath);
            Assert.That(asset, Is.Not.Null, "Expected Unity fixture asset: " + assetPath);
            return asset;
        }

        private static void RequireFixture(string assetPath)
        {
            if (!AssetDatabase.IsValidFolder(assetPath) && AssetDatabase.LoadAssetAtPath<Object>(assetPath) == null)
            {
                Assert.Ignore("Unity demo fixture is not imported: " + assetPath);
            }
        }
    }
}
