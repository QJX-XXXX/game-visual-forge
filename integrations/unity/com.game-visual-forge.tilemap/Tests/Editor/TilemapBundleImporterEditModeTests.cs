using System.Linq;
using GameVisualForge.Unity;
using NUnit.Framework;
using UnityEditor;
using UnityEngine;
using UnityEngine.Tilemaps;

namespace GameVisualForge.Unity.Tests
{
    public sealed class TilemapBundleImporterEditModeTests
    {
        private const string MapRoot = "Assets/GameVisualForgeMaps/autumn-creek-map";
        private const string TileRoot = MapRoot + "/Tiles";
        private const string TilemapPrefabPath = MapRoot + "/Prefabs/autumn-creek-map-tilemap.prefab";
        private const string PalettePrefabPath = MapRoot + "/Palettes/Autumn Creek Map Palette.prefab";

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
