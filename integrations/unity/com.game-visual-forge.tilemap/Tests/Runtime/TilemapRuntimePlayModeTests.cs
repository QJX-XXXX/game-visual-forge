using System.Collections;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;
using UnityEngine.Tilemaps;

namespace GameVisualForge.Unity.Tests
{
    public sealed class TilemapRuntimePlayModeTests
    {
        [UnityTest]
        public IEnumerator RuntimeTilemapCanRenderTiles()
        {
            var root = new GameObject("GameVisualForge Runtime Tilemap Fixture");
            var tilemapObject = new GameObject("Runtime Tilemap");
            tilemapObject.transform.SetParent(root.transform, false);
            var tilemap = tilemapObject.AddComponent<Tilemap>();
            var renderer = tilemapObject.AddComponent<TilemapRenderer>();
            var tile = ScriptableObject.CreateInstance<Tile>();

            try
            {
                tilemap.SetTile(Vector3Int.zero, tile);

                Assert.That(tilemap.GetUsedTilesCount(), Is.EqualTo(1));
                Assert.That(renderer, Is.Not.Null);

                yield return null;
            }
            finally
            {
                Object.Destroy(root);
                Object.Destroy(tile);
            }
        }
    }
}
