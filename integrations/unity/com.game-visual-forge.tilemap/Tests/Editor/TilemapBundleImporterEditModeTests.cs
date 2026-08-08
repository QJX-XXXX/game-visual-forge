using System;
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
        private const string MultiPageBundleRoot = TestGeneratedRoot + "/MultiPageBundle";
        private const string MultiPageGeneratedRoot = TestGeneratedRoot + "/MultiPage";
        private const string LegacyBundleRoot = TestGeneratedRoot + "/LegacyBundle";
        private const string LegacyGeneratedRoot = TestGeneratedRoot + "/LegacySinglePage";
        private string _task3Root;
        private string _task3BundleRoot;
        private string _task3GeneratedRoot;
        private string _task7Root;
        private string _task7BundleRoot;
        private string _task7GeneratedRoot;
        private string _task7PlacementPrefabPath;

        [SetUp]
        public void SetUp()
        {
            _task3Root = "Assets/GameVisualForgeTask3_" + SafeAssetName(TestContext.CurrentContext.Test.Name) + "_" + Guid.NewGuid().ToString("N");
            _task3BundleRoot = _task3Root + "/Bundle";
            _task3GeneratedRoot = _task3Root + "/Generated";
            DeleteTask3Fixtures();
            _task7Root = "Assets/GameVisualForgeTask7_" + SafeAssetName(TestContext.CurrentContext.Test.Name) + "_" + Guid.NewGuid().ToString("N");
            _task7BundleRoot = _task7Root + "/Bundle";
            _task7GeneratedRoot = _task7Root + "/Generated";
            _task7PlacementPrefabPath = _task7GeneratedRoot + "/Prefabs/task-7-placement-report-tilemap.prefab";
            RemoveTask7SceneInstances();
            DeleteTask7Fixtures();
        }

        [TearDown]
        public void TearDown()
        {
            DeleteTask3Fixtures();
            RemoveTask7SceneInstances();
            DeleteTask7Fixtures();
        }

        [OneTimeTearDown]
        public void OneTimeTearDown()
        {
            DeleteAssetIfExists(MultiPageBundleRoot);
            DeleteAssetIfExists(MultiPageGeneratedRoot);
            DeleteAssetIfExists(LegacyBundleRoot);
            DeleteAssetIfExists(LegacyGeneratedRoot);
            DeleteTask3Fixtures();
            DeleteTask7Fixtures();
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
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(result.tilemap_prefab);
            Assert.That(palette.GetComponentInChildren<Tilemap>(true).GetUsedTilesCount(), Is.EqualTo(16));
            Assert.That(palette.GetComponent<Grid>().cellSize, Is.EqualTo(Vector3.one));
            Assert.That(prefab.GetComponent<Grid>().cellSize, Is.EqualTo(Vector3.one));
        }

        [TestCase(16, 16, 16, 1f, 1f)]
        [TestCase(32, 32, 32, 1f, 1f)]
        [TestCase(16, 18, 16, 1f, 1.125f)]
        public void ImportBundleUsesDeclaredTileDimensionsForPaletteAndPrefabGrids(int tileWidth, int tileHeight, int pixelsPerUnit, float expectedCellWidth, float expectedCellHeight)
        {
            var result = TilemapBundleImporter.ImportBundle(CreateTileSizeBundleFixture(tileWidth, tileHeight, pixelsPerUnit, false));
            var expectedCellSize = new Vector3(expectedCellWidth, expectedCellHeight, 1f);

            var palette = AssetDatabase.LoadAssetAtPath<GameObject>(result.palette_prefab);
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(result.tilemap_prefab);

            Assert.That(palette.GetComponent<Grid>().cellSize, Is.EqualTo(expectedCellSize));
            Assert.That(prefab.GetComponent<Grid>().cellSize, Is.EqualTo(expectedCellSize));
        }

        [Test]
        public void ImportBundleRejectsMismatchedSliceDimensionsBeforeCreatingGeneratedRoot()
        {
            var manifestPath = CreateTileSizeBundleFixture(16, 18, 16, true);

            var exception = Assert.Throws<InvalidOperationException>(() => TilemapBundleImporter.ImportBundle(manifestPath));

            Assert.That(exception.Message, Is.EqualTo("All Tile slices must use the same dimensions."));
            Assert.That(AssetDatabase.IsValidFolder(_task3GeneratedRoot), Is.False);
        }

        [Test]
        public void HybridObjectPlacementCentersSpriteOverTopLeftGridFootprint()
        {
            var placement = new ObjectPlacement { x = 0, y = 0, sorting_order = 100 };
            var asset = new ObjectAsset { footprint = new GridRectData { width = 4, height = 3 } };

            var position = TilemapObjectImporter.ResolvePlacementLocalPosition(placement, asset, 12, 1f, 1f);

            Assert.That(position, Is.EqualTo(new Vector3(2f, 10.5f, 0.1f)));
        }

        [Test]
        public void HybridObjectColliderCentersCellsRelativeToSpritePivot()
        {
            var footprint = new GridRectData { width = 4, height = 3 };

            var topLeft = TilemapObjectImporter.ResolveCollisionCellLocalPosition(new GridCellData { x = 0, y = 0 }, footprint, 1f, 1f);
            var doorwayRow = TilemapObjectImporter.ResolveCollisionCellLocalPosition(new GridCellData { x = 2, y = 2 }, footprint, 1f, 1f);

            Assert.That(topLeft, Is.EqualTo(new Vector3(-1.5f, 1f, 0f)));
            Assert.That(doorwayRow, Is.EqualTo(new Vector3(0.5f, -1f, 0f)));
        }

        [Test]
        public void AssetsOnlyImportDoesNotChangeActiveSceneRootsAndWritesReport()
        {
            var manifestPath = CreateTask7BundleFixture(_task7BundleRoot, _task7GeneratedRoot);
            var reportPath = _task7GeneratedRoot + "/Reports/unity-import-report.json";
            var scene = SceneManager.GetActiveScene();
            var before = SceneManager.GetActiveScene().GetRootGameObjects().Select(item => item.GetInstanceID()).ToArray();
            var wasDirty = scene.isDirty;

            var result = TilemapBundleImporter.ImportBundle(manifestPath, ImportMode.AssetsOnly);

            var after = SceneManager.GetActiveScene().GetRootGameObjects().Select(item => item.GetInstanceID()).ToArray();
            Assert.That(after, Is.EqualTo(before));
            Assert.That(scene.isDirty, Is.EqualTo(wasDirty));
            Assert.That(result.scene_action, Is.EqualTo("unchanged"));
            Assert.That(result.scene_dirty, Is.EqualTo(wasDirty));
            Assert.That(result.scene_acceptance_status, Is.EqualTo("not_run"));
            Assert.That(result.scene_acceptance_report, Is.Null);
            Assert.That(result.unity_import_report, Is.EqualTo(reportPath));

            var report = ReadUnityReport(reportPath);
            Assert.That(report.python_quality_report, Is.EqualTo("quality-report.json"));
            Assert.That(report.python_quality_report_sha256, Is.EqualTo(ComputeSha256(Path.Combine(ToFullPath(_task7BundleRoot), "quality-report.json"))));
            Assert.That(report.atlas_page_count, Is.EqualTo(2));
            Assert.That(report.atlas_page_paths, Is.EqualTo(result.tileset_assets));
            Assert.That(report.tile_count, Is.EqualTo(32));
            Assert.That(report.tile_paths, Is.EqualTo(result.tile_assets));
            Assert.That(report.palette_path, Is.EqualTo(result.palette_prefab));
            Assert.That(report.prefab_path, Is.EqualTo(result.tilemap_prefab));
            Assert.That(report.scene_action, Is.EqualTo("unchanged"));
            Assert.That(report.scene_dirty, Is.EqualTo(wasDirty));
            Assert.That(report.had_existing_assets, Is.False);
            Assert.That(report.resource_guids_stable, Is.True);
        }

        [Test]
        public void ImportAndPlaceReusesExistingPrefabInstanceAndReportsStableExistingAssets()
        {
            var manifestPath = CreateTask7BundleFixture(_task7BundleRoot, _task7GeneratedRoot);
            var reportPath = _task7GeneratedRoot + "/Reports/unity-import-report.json";

            var first = TilemapBundleImporter.ImportBundle(manifestPath, ImportMode.ImportAndPlace);
            var firstGuids = CaptureGuids(new[] { first.tileset_assets[0], first.tile_assets[0], first.palette_prefab, first.tilemap_prefab });
            var firstReport = ReadUnityReport(reportPath);
            var second = TilemapBundleImporter.ImportBundle(manifestPath, ImportMode.ImportAndPlace);
            var secondReport = ReadUnityReport(reportPath);
            var matches = SceneManager.GetActiveScene().GetRootGameObjects()
                .Count(root => PrefabUtility.GetPrefabAssetPathOfNearestInstanceRoot(root) == second.tilemap_prefab);

            Assert.That(first.scene_action, Is.EqualTo("placed"));
            Assert.That(first.scene_acceptance_status, Is.EqualTo("passed"));
            Assert.That(first.scene_acceptance_report, Is.EqualTo(_task7GeneratedRoot + "/Reports/unity-scene-acceptance.json"));
            Assert.That(firstReport.scene_action, Is.EqualTo("placed"));
            Assert.That(firstReport.had_existing_assets, Is.False);
            Assert.That(matches, Is.EqualTo(1));
            Assert.That(second.scene_action, Is.EqualTo("updated"));
            Assert.That(second.scene_acceptance_status, Is.EqualTo("passed"));
            Assert.That(second.scene_dirty, Is.True);
            Assert.That(secondReport.scene_action, Is.EqualTo("updated"));
            Assert.That(secondReport.had_existing_assets, Is.True);
            Assert.That(secondReport.resource_guids_stable, Is.True);
            foreach (var item in firstGuids)
                Assert.That(AssetDatabase.AssetPathToGUID(item.Key), Is.EqualTo(item.Value), item.Key);
        }

        private static string CreateTwoPageBundleFixture()
        {
            var bundleFullPath = ToFullPath(MultiPageBundleRoot);
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

        private string CreateTileSizeBundleFixture(int tileWidth, int tileHeight, int pixelsPerUnit, bool includeMismatchedSlice)
        {
            var bundleFullPath = ToFullPath(_task3BundleRoot);
            Directory.CreateDirectory(bundleFullPath);

            var texture = new Texture2D(tileWidth * 2, tileHeight, TextureFormat.RGBA32, false);
            try
            {
                for (var y = 0; y < texture.height; y++)
                {
                    for (var x = 0; x < texture.width; x++)
                        texture.SetPixel(x, y, new Color32(64, 128, 192, 255));
                }
                texture.Apply();
                File.WriteAllBytes(Path.Combine(bundleFullPath, "tileset.png"), texture.EncodeToPNG());
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(texture);
            }

            var secondWidth = includeMismatchedSlice ? tileWidth - 1 : tileWidth;
            File.WriteAllText(Path.Combine(bundleFullPath, "slices.json"), @"{
  ""schema_version"": 1,
  ""tiles"": [
    { ""id"": ""tile-00"", ""rect"": { ""x"": 0, ""y"": 0, ""width"": " + tileWidth + @", ""height"": " + tileHeight + @" }, ""palette"": { ""x"": 0, ""y"": 0 }, ""collider_type"": ""none"" },
    { ""id"": ""tile-01"", ""rect"": { ""x"": " + tileWidth + @", ""y"": 0, ""width"": " + secondWidth + @", ""height"": " + tileHeight + @" }, ""palette"": { ""x"": 1, ""y"": 0 }, ""collider_type"": ""none"" }
  ]
}");
            File.WriteAllText(Path.Combine(bundleFullPath, "placement.json"), @"{
  ""schema_version"": 1,
  ""map_size"": { ""width"": 1, ""height"": 1 },
  ""layers"": [
    { ""id"": ""ground"", ""sorting_order"": 0, ""has_collider"": false, ""placements"": [ { ""x"": 0, ""y"": 0, ""tile_id"": ""tile-00"" } ] }
  ]
}");
            var manifestPath = Path.Combine(bundleFullPath, "manifest.json");
            File.WriteAllText(manifestPath, @"{
  ""schema_version"": 1,
  ""asset_id"": ""task-3-tile-size-fixture"",
  ""engine_target"": ""Unity_Tilemap"",
  ""tileset"": ""tileset.png"",
  ""slices"": ""slices.json"",
  ""placement"": ""placement.json"",
  ""generated_root"": """ + _task3GeneratedRoot + @""",
  ""pixels_per_unit"": " + pixelsPerUnit + @",
  ""tile_width"": " + tileWidth + @",
  ""tile_height"": " + tileHeight + @",
  ""filter_mode"": ""point"",
  ""palette_name"": ""Task 3 Palette"",
  ""prefab_name"": ""task-3-tilemap""
}");

            AssetDatabase.Refresh();
            return manifestPath;
        }

        private static string CreateTask7BundleFixture(string bundleRoot, string generatedRoot)
        {
            var bundleFullPath = ToFullPath(bundleRoot);
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
  ""generated_root"": """ + generatedRoot + @""",
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
            var bundleFullPath = ToFullPath(LegacyBundleRoot);
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
                UnityEngine.Object.DestroyImmediate(texture);
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

        private static UnityImportReport ReadUnityReport(string reportPath)
        {
            var report = AssetDatabase.LoadAssetAtPath<TextAsset>(reportPath);
            Assert.That(report, Is.Not.Null, "Expected Unity import report: " + reportPath);
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

        private static string SafeAssetName(string value)
        {
            var builder = new StringBuilder(value.Length);
            foreach (var character in value)
                builder.Append(char.IsLetterOrDigit(character) ? character : '_');
            return builder.ToString();
        }

        private void RemoveTask7SceneInstances()
        {
            if (string.IsNullOrEmpty(_task7PlacementPrefabPath))
                return;
            foreach (var root in SceneManager.GetActiveScene().GetRootGameObjects().ToArray())
            {
                if (PrefabUtility.GetPrefabAssetPathOfNearestInstanceRoot(root) == _task7PlacementPrefabPath)
                    UnityEngine.Object.DestroyImmediate(root);
            }
        }

        private void DeleteTask3Fixtures()
        {
            if (!string.IsNullOrEmpty(_task3Root))
                DeleteAssetIfExists(_task3Root);
        }

        private void DeleteTask7Fixtures()
        {
            if (!string.IsNullOrEmpty(_task7Root))
                DeleteAssetIfExists(_task7Root);
        }

        private static void DeleteAssetIfExists(string assetPath)
        {
            if (AssetDatabase.IsValidFolder(assetPath) || AssetDatabase.LoadAssetAtPath<UnityEngine.Object>(assetPath) != null)
                AssetDatabase.DeleteAsset(assetPath);
            var fullPath = ToFullPath(assetPath);
            if (Directory.Exists(fullPath))
                Directory.Delete(fullPath, true);
            var metaPath = fullPath + ".meta";
            if (File.Exists(metaPath))
                File.Delete(metaPath);
            AssetDatabase.Refresh();
        }

        private static T LoadFixture<T>(string assetPath) where T : UnityEngine.Object
        {
            RequireFixture(assetPath);
            var asset = AssetDatabase.LoadAssetAtPath<T>(assetPath);
            Assert.That(asset, Is.Not.Null, "Expected Unity fixture asset: " + assetPath);
            return asset;
        }

        private static void RequireFixture(string assetPath)
        {
            if (!AssetDatabase.IsValidFolder(assetPath) && AssetDatabase.LoadAssetAtPath<UnityEngine.Object>(assetPath) == null)
            {
                Assert.Ignore("Unity demo fixture is not imported: " + assetPath);
            }
        }
    }
}
