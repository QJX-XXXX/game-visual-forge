using System.Collections;
using NUnit.Framework;
using UnityEditor;
using UnityEngine;
using UnityEngine.TestTools;
using UnityEngine.Tilemaps;

namespace GameVisualForge.Unity.Tests
{
    public sealed class TilemapPrefabPlayModeTests
    {
        private const string TilemapPrefabPath = "Assets/GameVisualForgeMaps/autumn-creek-map/Prefabs/autumn-creek-map-tilemap.prefab";

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
    }
}
