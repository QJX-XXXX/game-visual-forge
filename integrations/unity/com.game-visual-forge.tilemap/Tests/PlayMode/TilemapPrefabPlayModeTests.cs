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
        public IEnumerator AutumnCreekPrefabIsRenderableAtRuntime()
        {
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(TilemapPrefabPath);
            if (prefab == null)
            {
                Assert.Ignore("Unity demo fixture is not imported: " + TilemapPrefabPath);
            }

            var root = Object.Instantiate(prefab);
            if (root == null)
            {
                Assert.Fail("The Tilemap Prefab could not be instantiated.");
            }

            try
            {
                var tilemaps = root.GetComponentsInChildren<Tilemap>(true);

                Assert.That(tilemaps, Has.Length.EqualTo(3));
                Assert.That(root.GetComponentInChildren<TilemapRenderer>(true), Is.Not.Null);
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
