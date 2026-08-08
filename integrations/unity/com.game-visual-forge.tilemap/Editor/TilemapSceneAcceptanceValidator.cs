using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.Tilemaps;

namespace GameVisualForge.Unity
{
    internal static class TilemapSceneAcceptanceValidator
    {
        [Serializable]
        internal sealed class SceneAcceptanceCheck
        {
            public string id;
            public string status;
            public string message;
        }

        [Serializable]
        internal sealed class SceneAcceptanceResult
        {
            public int schema_version = 1;
            public string status;
            public string scene_path;
            public int root_count;
            public int tile_count;
            public int object_count;
            public SceneAcceptanceCheck[] checks;
            public string report_path;
        }

        [Serializable] private sealed class CollisionManifest { public int schema_version; public BlockedCell[] blocked_cells; public TerrainBlockedCell[] terrain_blocked_cells; public CollisionEntrance[] entrances; public BridgeRuleData[] bridge_connectivity_rules; }
        [Serializable] private sealed class BlockedCell { public int x; public int y; public string instance_id; }
        [Serializable] private sealed class TerrainBlockedCell { public int x; public int y; public string layer_id; public string tile_id; }
        [Serializable] private sealed class CollisionEntrance { public GridCellData cell; }
        [Serializable] private sealed class BridgeRuleData { public string id; public string orientation; public GridCellData start; public GridCellData end; public bool traversable = true; }

        internal static SceneAcceptanceResult ValidateAndWrite(
            string manifestFullPath,
            BundleManifest manifest,
            string prefabPath,
            PlacementManifest placement,
            ObjectManifest objectManifest,
            Vector3 gridCellSize,
            ImportMode mode)
        {
            if (mode == ImportMode.AssetsOnly)
                return new SceneAcceptanceResult { status = "not_run", scene_path = SceneManager.GetActiveScene().path, checks = Array.Empty<SceneAcceptanceCheck>(), report_path = null };

            var scene = SceneManager.GetActiveScene();
            var roots = scene.GetRootGameObjects().Where(root => string.Equals(PrefabUtility.GetPrefabAssetPathOfNearestInstanceRoot(root), prefabPath, StringComparison.Ordinal)).ToArray();
            var checks = new List<SceneAcceptanceCheck>();
            var failures = new List<string>();
            AddCheck(checks, failures, "duplicate-root", roots.Length == 1, $"expected one owned prefab root, found {roots.Length}");
            var root = roots.FirstOrDefault();
            var tilemaps = root == null ? Array.Empty<Tilemap>() : root.GetComponentsInChildren<Tilemap>(true);
            var actualTileCount = tilemaps.Sum(tilemap => tilemap.GetUsedTilesCount());
            var expectedTileCount = placement.layers == null ? 0 : placement.layers.Sum(layer => layer.placements == null ? 0 : layer.placements.Length);
            AddCheck(checks, failures, "tile-count", actualTileCount == expectedTileCount, $"expected {expectedTileCount} placed tiles, found {actualTileCount}");

            var expectedObjects = objectManifest == null || objectManifest.placements == null ? 0 : objectManifest.placements.Length;
            var objectInstances = root == null ? Array.Empty<Transform>() : root.GetComponentsInChildren<Transform>(true).Where(item => item.parent != null && (item.parent.name == "Buildings" || item.parent.name == "Props")).ToArray();
            AddCheck(checks, failures, "object-count", objectInstances.Length == expectedObjects, $"expected {expectedObjects} object instances, found {objectInstances.Length}");
            ValidateObjects(checks, failures, root, objectManifest, placement.map_size, gridCellSize);

            CollisionManifest collision = null;
            if (!string.IsNullOrWhiteSpace(manifest.collision))
                collision = ReadJson<CollisionManifest>(ResolveBundleFile(Path.GetDirectoryName(manifestFullPath), manifest.collision));
            ValidateCollision(checks, failures, root, tilemaps, placement, collision, gridCellSize);

            var result = new SceneAcceptanceResult
            {
                status = failures.Count == 0 ? "passed" : "failed",
                scene_path = scene.path,
                root_count = roots.Length,
                tile_count = actualTileCount,
                object_count = objectInstances.Length,
                checks = checks.ToArray(),
            };
            var reportAssetPath = $"{manifest.generated_root}/Reports/unity-scene-acceptance.json";
            TilemapBundleImporter.EnsureAssetFolder($"{manifest.generated_root}/Reports");
            result.report_path = reportAssetPath;
            File.WriteAllText(TilemapBundleImporter.AssetPathToFullPath(reportAssetPath), JsonUtility.ToJson(result, true));
            AssetDatabase.ImportAsset(reportAssetPath, ImportAssetOptions.ForceUpdate);
            if (failures.Count != 0)
                throw new InvalidOperationException("Unity scene acceptance failed: " + string.Join("; ", failures));
            return result;
        }

        private static void ValidateObjects(List<SceneAcceptanceCheck> checks, List<string> failures, GameObject root, ObjectManifest manifest, MapSize mapSize, Vector3 cellSize)
        {
            if (root == null || manifest == null || manifest.placements == null)
                return;
            foreach (var placement in manifest.placements)
            {
                var asset = manifest.assets.FirstOrDefault(item => item.id == placement.asset_id);
                var instance = root.GetComponentsInChildren<Transform>(true).FirstOrDefault(item => item.name == placement.id);
                var expected = asset == null ? Vector3.zero : TilemapObjectImporter.ResolvePlacementLocalPosition(placement, asset, mapSize.height, cellSize.x, cellSize.y);
                AddCheck(checks, failures, $"object-transform-{placement.id}", instance != null && Vector3.Distance(instance.localPosition, expected) < 0.001f, $"object {placement.id} transform does not match the top-left placement");
                if (instance == null || asset == null)
                    continue;
                var sprite = instance.GetComponentInChildren<SpriteRenderer>(true);
                AddCheck(checks, failures, $"object-bounds-{placement.id}", sprite != null && sprite.bounds.min.x >= root.transform.position.x - 0.001f && sprite.bounds.min.y >= root.transform.position.y - 0.001f, $"object {placement.id} Sprite bounds are outside the scene footprint");
                foreach (var cell in asset.collision_cells ?? Array.Empty<GridCellData>())
                {
                    var collider = instance.Find($"Collision-{cell.x}-{cell.y}")?.GetComponent<BoxCollider2D>();
                    AddCheck(checks, failures, $"object-collider-{placement.id}-{cell.x}-{cell.y}", collider != null && Vector2.Distance(collider.size, new Vector2(cellSize.x, cellSize.y)) < 0.001f, $"object {placement.id} collider does not match its declared cell");
                }
            }
        }

        private static void ValidateCollision(List<SceneAcceptanceCheck> checks, List<string> failures, GameObject root, Tilemap[] tilemaps, PlacementManifest placement, CollisionManifest collision, Vector3 cellSize)
        {
            if (collision == null || root == null)
                return;
            var collidableMaps = tilemaps.Where(item => item.GetComponent<TilemapCollider2D>() != null).ToArray();
            foreach (var cell in collision.terrain_blocked_cells ?? Array.Empty<TerrainBlockedCell>())
            {
                var unityCell = new Vector3Int(cell.x, placement.map_size.height - 1 - cell.y, 0);
                AddCheck(checks, failures, $"terrain-blocker-{cell.x}-{cell.y}", collidableMaps.Any(map => map.HasTile(unityCell)), $"terrain blocked cell ({cell.x},{cell.y}) has no collidable Unity tile");
            }
            foreach (var entrance in collision.entrances ?? Array.Empty<CollisionEntrance>())
            {
                var unityCell = new Vector3Int(entrance.cell.x, placement.map_size.height - 1 - entrance.cell.y, 0);
                var blocked = collidableMaps.Any(map => map.GetColliderType(unityCell) != Tile.ColliderType.None);
                AddCheck(checks, failures, $"doorway-{entrance.cell.x}-{entrance.cell.y}", !blocked, $"doorway cell ({entrance.cell.x},{entrance.cell.y}) is blocked");
            }
            foreach (var bridge in collision.bridge_connectivity_rules ?? Array.Empty<BridgeRuleData>())
            {
                if (!bridge.traversable || bridge.start == null || bridge.end == null)
                    continue;
                var coordinates = bridge.orientation == "horizontal" ? Enumerable.Range(Mathf.Min(bridge.start.x, bridge.end.x), Mathf.Abs(bridge.end.x - bridge.start.x) + 1).Select(x => new GridCellData { x = x, y = bridge.start.y }) : Enumerable.Range(Mathf.Min(bridge.start.y, bridge.end.y), Mathf.Abs(bridge.end.y - bridge.start.y) + 1).Select(y => new GridCellData { x = bridge.start.x, y = y });
                var blocked = (collision.terrain_blocked_cells ?? Array.Empty<TerrainBlockedCell>()).Any(cell => coordinates.Any(item => item.x == cell.x && item.y == cell.y));
                AddCheck(checks, failures, $"bridge-{bridge.id}", !blocked, $"traversable bridge {bridge.id} overlaps terrain blockers");
            }
        }

        private static void AddCheck(List<SceneAcceptanceCheck> checks, List<string> failures, string id, bool passed, string message)
        {
            checks.Add(new SceneAcceptanceCheck { id = id, status = passed ? "passed" : "failed", message = message });
            if (!passed) failures.Add(message);
        }

        private static T ReadJson<T>(string path)
        {
            if (!File.Exists(path)) throw new FileNotFoundException("Scene acceptance input was not found.", path);
            return JsonUtility.FromJson<T>(File.ReadAllText(path));
        }

        private static string ResolveBundleFile(string bundleDirectory, string relativePath)
        {
            if (string.IsNullOrWhiteSpace(bundleDirectory) || Path.IsPathRooted(relativePath)) throw new InvalidOperationException("Bundle collision paths must be relative.");
            var root = Path.GetFullPath(bundleDirectory).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) + Path.DirectorySeparatorChar;
            var resolved = Path.GetFullPath(Path.Combine(bundleDirectory, relativePath));
            if (!resolved.StartsWith(root, StringComparison.OrdinalIgnoreCase)) throw new InvalidOperationException("Bundle collision paths must remain inside the bundle.");
            return resolved;
        }
    }
}
