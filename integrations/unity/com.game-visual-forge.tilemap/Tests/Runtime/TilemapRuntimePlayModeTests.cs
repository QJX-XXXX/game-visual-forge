using System.Collections;
using System.Linq;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;
using UnityEngine.Tilemaps;

namespace GameVisualForge.Unity.Tests
{
    public sealed class TilemapRuntimePlayModeTests
    {
        [UnityTest]
        public IEnumerator ImportedTilemapsRemainRenderableAtRuntime()
        {
            var tilemaps = Object.FindObjectsOfType<Tilemap>();
            if (tilemaps.Length == 0)
                Assert.Ignore("The active Unity scene has no Tilemap fixture loaded.");

            Assert.That(tilemaps.Any(tilemap => tilemap.GetUsedTilesCount() > 0), Is.True);
            Assert.That(tilemaps.Any(tilemap => tilemap.GetComponent<TilemapRenderer>() != null), Is.True);
            yield return null;
        }
    }
}
