using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

namespace GameVisualForge.Unity
{
    internal sealed class ObjectImportResult
    {
        public string objects_manifest;
        public string collision_manifest;
        public string[] object_prefabs;
        public int object_count;
    }

    internal static class TilemapObjectImporter
    {
        internal static ObjectImportResult ImportObjects(string bundleRoot, string generatedRoot, ObjectManifest manifest, int mapHeight, float cellWidth, float cellHeight, string collisionManifestPath)
        {
            if (manifest == null || manifest.schema_version != 1 || manifest.assets == null || manifest.placements == null)
                throw new InvalidOperationException("Hybrid object manifest must use schema_version 1 and contain assets and placements.");
            var textureFolder = $"{generatedRoot}/Objects";
            var prefabFolder = $"{generatedRoot}/Prefabs/Objects";
            var dataFolder = $"{generatedRoot}/Data";
            TilemapBundleImporter.EnsureAssetFolder(textureFolder);
            TilemapBundleImporter.EnsureAssetFolder(prefabFolder);
            TilemapBundleImporter.EnsureAssetFolder(dataFolder);
            var prefabs = new Dictionary<string, string>(StringComparer.Ordinal);
            foreach (var asset in manifest.assets)
            {
                if (string.IsNullOrWhiteSpace(asset.id) || string.IsNullOrWhiteSpace(asset.path))
                    throw new InvalidOperationException("Every object asset must define id and path.");
                var texturePath = $"{textureFolder}/{asset.id}.png";
                CopyToAsset(bundleRoot, asset.path, texturePath);
                ConfigureObjectTexture(texturePath, asset.pixels_per_unit);
                var sprite = AssetDatabase.LoadAssetAtPath<Sprite>(texturePath) ?? throw new InvalidOperationException($"Object Sprite '{asset.id}' was not imported.");
                var prefabPath = $"{prefabFolder}/{asset.id}.prefab";
                CreateOrUpdateObjectPrefab(prefabPath, sprite, asset, cellWidth, cellHeight);
                prefabs[asset.id] = prefabPath;
            }
            var output = new ObjectImportResult
            {
                objects_manifest = "tilemap-objects.json",
                collision_manifest = collisionManifestPath,
                object_prefabs = prefabs.Values.ToArray(),
                object_count = manifest.placements.Length,
            };
            return output;
        }

        internal static void AttachObjects(string prefabPath, ObjectManifest manifest, IReadOnlyDictionary<string, string> prefabPaths, int mapHeight, float cellWidth, float cellHeight)
        {
            var root = PrefabUtility.LoadPrefabContents(prefabPath);
            try
            {
                var buildings = EnsureGroup(root.transform, "Buildings");
                var props = EnsureGroup(root.transform, "Props");
                foreach (var child in new[] { buildings, props })
                    for (var index = child.childCount - 1; index >= 0; index--)
                        UnityEngine.Object.DestroyImmediate(child.GetChild(index).gameObject);
                foreach (var placement in manifest.placements)
                {
                    var asset = manifest.assets.FirstOrDefault(item => item.id == placement.asset_id) ?? throw new InvalidOperationException($"Object placement references unknown asset '{placement.asset_id}'.");
                    var source = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPaths[asset.id]);
                    var parent = asset.kind == "building" ? buildings : props;
                    var instance = (GameObject)PrefabUtility.InstantiatePrefab(source, parent);
                    instance.name = placement.id;
                    instance.transform.localPosition = ResolvePlacementLocalPosition(placement, asset, mapHeight, cellWidth, cellHeight);
                    foreach (var renderer in instance.GetComponentsInChildren<SpriteRenderer>(true))
                        renderer.sortingOrder = placement.sorting_order;
                }
                PrefabUtility.SaveAsPrefabAsset(root, prefabPath);
            }
            finally { PrefabUtility.UnloadPrefabContents(root); }
        }

        private static Transform EnsureGroup(Transform root, string name)
        {
            var existing = root.Find(name);
            if (existing != null) return existing;
            var group = new GameObject(name);
            group.transform.SetParent(root, false);
            return group.transform;
        }

        private static void ConfigureObjectTexture(string assetPath, int pixelsPerUnit)
        {
            var importer = AssetImporter.GetAtPath(assetPath) as TextureImporter ?? throw new InvalidOperationException($"TextureImporter was not found for {assetPath}.");
            importer.textureType = TextureImporterType.Sprite;
            importer.spriteImportMode = SpriteImportMode.Single;
            importer.spritePixelsPerUnit = pixelsPerUnit > 0 ? pixelsPerUnit : 32;
            importer.filterMode = FilterMode.Point;
            importer.mipmapEnabled = false;
            importer.alphaIsTransparency = true;
            importer.textureCompression = TextureImporterCompression.Uncompressed;
            importer.SaveAndReimport();
        }

        private static void CreateOrUpdateObjectPrefab(string path, Sprite sprite, ObjectAsset asset, float cellWidth, float cellHeight)
        {
            var root = new GameObject(asset.id);
            var renderer = root.AddComponent<SpriteRenderer>();
            renderer.sprite = sprite;
            renderer.sortingOrder = 0;
            if (asset.collision_cells != null)
            {
                foreach (var cell in asset.collision_cells)
                {
                    var colliderObject = new GameObject($"Collision-{cell.x}-{cell.y}");
                    colliderObject.transform.SetParent(root.transform, false);
                    colliderObject.transform.localPosition = ResolveCollisionCellLocalPosition(cell, asset.footprint, cellWidth, cellHeight);
                    var collider = colliderObject.AddComponent<BoxCollider2D>();
                    collider.size = new Vector2(cellWidth, cellHeight);
                }
            }
            PrefabUtility.SaveAsPrefabAsset(root, path);
            UnityEngine.Object.DestroyImmediate(root);
        }

        internal static Vector3 ResolvePlacementLocalPosition(ObjectPlacement placement, ObjectAsset asset, int mapHeight, float cellWidth, float cellHeight)
        {
            if (asset?.footprint == null || asset.footprint.width <= 0 || asset.footprint.height <= 0)
                throw new InvalidOperationException("Object assets require a positive footprint before placement.");
            return new Vector3(
                (placement.x + asset.footprint.width * 0.5f) * cellWidth,
                (mapHeight - placement.y - asset.footprint.height * 0.5f) * cellHeight,
                placement.sorting_order * 0.001f);
        }

        internal static Vector3 ResolveCollisionCellLocalPosition(GridCellData cell, GridRectData footprint, float cellWidth, float cellHeight)
        {
            if (footprint == null || footprint.width <= 0 || footprint.height <= 0)
                throw new InvalidOperationException("Object assets require a positive footprint before collider placement.");
            return new Vector3(
                (cell.x + 0.5f - footprint.width * 0.5f) * cellWidth,
                (footprint.height * 0.5f - cell.y - 0.5f) * cellHeight,
                0f);
        }

        private static void CopyToAsset(string bundleRoot, string relativePath, string assetPath)
        {
            if (Path.IsPathRooted(relativePath)) throw new InvalidOperationException("Object paths must be relative bundle files.");
            var root = Path.GetFullPath(bundleRoot).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) + Path.DirectorySeparatorChar;
            var source = Path.GetFullPath(Path.Combine(bundleRoot, relativePath));
            if (!source.StartsWith(root, StringComparison.OrdinalIgnoreCase) || !File.Exists(source))
                throw new FileNotFoundException("Object image was not found.", source);
            var destination = TilemapBundleImporter.AssetPathToFullPath(assetPath);
            Directory.CreateDirectory(Path.GetDirectoryName(destination));
            File.Copy(source, destination, true);
            AssetDatabase.ImportAsset(assetPath, ImportAssetOptions.ForceSynchronousImport | ImportAssetOptions.ForceUpdate);
        }
    }
}
