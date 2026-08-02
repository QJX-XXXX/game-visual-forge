using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Tilemaps;
using UnityEditor.U2D.Sprites;
using UnityEngine;
using UnityEngine.Tilemaps;

namespace GameVisualForge.Unity
{
    public static partial class TilemapBundleImporter
    {
        [MenuItem("Tools/Game Visual Forge/Import Tilemap Bundle...")]
        private static void ImportFromMenu()
        {
            ImportFromMenu(ImportMode.AssetsOnly);
        }

        [MenuItem("Tools/Game Visual Forge/Import and Place Tilemap Bundle...")]
        private static void ImportAndPlaceFromMenu()
        {
            ImportFromMenu(ImportMode.ImportAndPlace);
        }

        private static void ImportFromMenu(ImportMode mode)
        {
            var manifestPath = EditorUtility.OpenFilePanel("Import Game Visual Forge Tilemap Bundle", "", "json");
            if (string.IsNullOrEmpty(manifestPath))
                return;

            try
            {
                var result = ImportBundle(manifestPath, mode);
                EditorUtility.DisplayDialog("Game Visual Forge", $"Imported {result.asset_id}\n{result.tilemap_prefab}", "OK");
            }
            catch (Exception exception)
            {
                Debug.LogException(exception);
                EditorUtility.DisplayDialog("Game Visual Forge import failed", exception.Message, "OK");
            }
        }

        public static string ImportBundleForAutomation(string manifestPath)
        {
            return JsonUtility.ToJson(ImportBundle(manifestPath, ImportMode.AssetsOnly));
        }

        public static string ImportAndPlaceBundleForAutomation(string manifestPath)
        {
            return JsonUtility.ToJson(ImportBundle(manifestPath, ImportMode.ImportAndPlace));
        }

        public static ImportResult ImportBundle(string manifestPath)
        {
            return ImportBundle(manifestPath, ImportMode.AssetsOnly);
        }

        public static ImportResult ImportBundle(string manifestPath, ImportMode mode)
        {
            var manifestFullPath = ResolveInputPath(manifestPath);
            var manifest = ReadJson<BundleManifest>(manifestFullPath);
            ValidateManifest(manifest);

            var bundleDirectory = Path.GetDirectoryName(manifestFullPath) ?? throw new InvalidOperationException("Bundle manifest has no parent directory.");
            var slices = ReadJson<SliceManifest>(Path.Combine(bundleDirectory, manifest.slices));
            var placement = ReadJson<PlacementManifest>(Path.Combine(bundleDirectory, manifest.placement));
            ValidateBundleData(slices, placement);
            var isLegacySinglePage = manifest.tilesets == null || manifest.tilesets.Length == 0;
            var atlasPages = NormalizeAtlasPages(manifest);

            EnsureAssetFolder(manifest.generated_root);
            var textureFolder = $"{manifest.generated_root}/Textures";
            var tileFolder = $"{manifest.generated_root}/Tiles";
            var paletteFolder = $"{manifest.generated_root}/Palettes";
            var prefabFolder = $"{manifest.generated_root}/Prefabs";
            EnsureAssetFolder(textureFolder);
            EnsureAssetFolder(tileFolder);
            EnsureAssetFolder(paletteFolder);
            EnsureAssetFolder(prefabFolder);

            var tilesetAssets = new List<string>();
            var sprites = new Dictionary<string, Sprite>(StringComparer.Ordinal);
            foreach (var page in atlasPages)
            {
                var tilesetAssetPath = $"{textureFolder}/{page.atlas_id}.png";
                CopyToAsset(Path.Combine(bundleDirectory, page.path), tilesetAssetPath);
                var pageSlices = slices.tiles.Where(slice => SliceBelongsToPage(slice, page, isLegacySinglePage)).ToArray();
                ConfigureAndSliceTexture(tilesetAssetPath, manifest, pageSlices);
                foreach (var sprite in AssetDatabase.LoadAllAssetsAtPath(tilesetAssetPath).OfType<Sprite>())
                {
                    if (sprites.ContainsKey(sprite.name))
                        throw new InvalidOperationException($"Duplicate Sprite ID across atlas pages: {sprite.name}");
                    sprites.Add(sprite.name, sprite);
                }
                tilesetAssets.Add(tilesetAssetPath);
            }
            var tiles = CreateOrUpdateTiles(tileFolder, slices.tiles, sprites);
            var palettePath = CreateOrUpdatePalette(paletteFolder, manifest.palette_name, slices.tiles, tiles);
            var prefabPath = CreateOrUpdateTilemapPrefab(prefabFolder, manifest.prefab_name, placement.layers, tiles);

            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            Debug.Log($"[Game Visual Forge] Imported tilemap bundle '{manifest.asset_id}' to '{manifest.generated_root}'.");
            var result = new ImportResult
            {
                asset_id = manifest.asset_id,
                generated_root = manifest.generated_root,
                tileset_asset = tilesetAssets[0],
                tileset_assets = tilesetAssets.ToArray(),
                palette_prefab = palettePath,
                tilemap_prefab = prefabPath,
                tile_count = tiles.Count,
                layer_count = placement.layers.Length,
                scene_action = "unchanged",
                scene_path = UnityEditor.SceneManagement.EditorSceneManager.GetActiveScene().path,
                scene_dirty = false,
            };
            if (mode == ImportMode.ImportAndPlace)
            {
                var placementResult = TilemapScenePlacer.PlaceOrUpdate(prefabPath);
                result.scene_action = placementResult.scene_action;
                result.scene_path = placementResult.scene_path;
                result.scene_dirty = placementResult.scene_dirty;
            }
            var report = TilemapImportReportWriter.Write(manifestFullPath, result, atlasPages.Length, mode);
            return result;
        }

        private static AtlasPage[] NormalizeAtlasPages(BundleManifest manifest)
        {
            var atlasPages = manifest.tilesets != null && manifest.tilesets.Length > 0
                ? manifest.tilesets
                : new[] { new AtlasPage { atlas_id = "page-01", path = manifest.tileset } };
            if (atlasPages.Length < 1 || atlasPages.Length > 3)
                throw new InvalidOperationException("Unity tilemap bundles must contain one to three atlas pages.");
            if (atlasPages.Any(page => string.IsNullOrWhiteSpace(page.atlas_id) || string.IsNullOrWhiteSpace(page.path)))
                throw new InvalidOperationException("Every atlas page must define atlas_id and path.");
            if (atlasPages.Select(page => page.atlas_id).Distinct(StringComparer.Ordinal).Count() != atlasPages.Length)
                throw new InvalidOperationException("Atlas page IDs must be unique.");
            return atlasPages;
        }

        private static bool SliceBelongsToPage(TileSlice slice, AtlasPage page, bool isLegacySinglePage)
        {
            if (isLegacySinglePage && string.IsNullOrEmpty(slice.atlas_id))
                return page.atlas_id == "page-01";
            return slice.atlas_id == page.atlas_id;
        }

        private static T ReadJson<T>(string path)
        {
            if (!File.Exists(path))
                throw new FileNotFoundException("Game Visual Forge bundle file was not found.", path);
            var value = JsonUtility.FromJson<T>(File.ReadAllText(path));
            return value ?? throw new InvalidOperationException($"Could not parse JSON: {path}");
        }

        private static void ValidateManifest(BundleManifest manifest)
        {
            if (manifest.schema_version != 1 || manifest.engine_target != "Unity_Tilemap")
                throw new InvalidOperationException("Only schema_version 1 Unity_Tilemap bundles are supported.");
            if (string.IsNullOrWhiteSpace(manifest.asset_id) || (string.IsNullOrWhiteSpace(manifest.tileset) && (manifest.tilesets == null || manifest.tilesets.Length == 0)) || string.IsNullOrWhiteSpace(manifest.slices) || string.IsNullOrWhiteSpace(manifest.placement))
                throw new InvalidOperationException("The bundle manifest is missing required fields.");
            if (manifest.pixels_per_unit <= 0)
                throw new InvalidOperationException("pixels_per_unit must be positive.");
            ValidateAssetPath(manifest.generated_root);
        }

        private static void ValidateBundleData(SliceManifest slices, PlacementManifest placement)
        {
            if (slices.schema_version != 1 || placement.schema_version != 1 || slices.tiles == null || slices.tiles.Length == 0 || placement.layers == null || placement.layers.Length == 0)
                throw new InvalidOperationException("Tile slices and placement data must use schema_version 1 and contain data.");
            var tileIds = new HashSet<string>(slices.tiles.Select(tile => tile.id), StringComparer.Ordinal);
            if (tileIds.Count != slices.tiles.Length || tileIds.Contains(null))
                throw new InvalidOperationException("Tile IDs must be present and unique.");
            foreach (var layer in placement.layers)
            {
                if (layer.placements == null || layer.placements.Any(item => !tileIds.Contains(item.tile_id)))
                    throw new InvalidOperationException($"Layer '{layer.id}' references an unknown tile.");
            }
        }

        private static string ResolveInputPath(string path)
        {
            if (string.IsNullOrWhiteSpace(path))
                throw new ArgumentException("Manifest path must not be empty.", nameof(path));
            return Path.GetFullPath(path.StartsWith("Assets/", StringComparison.Ordinal) ? AssetPathToFullPath(path) : path);
        }

        private static void ValidateAssetPath(string path)
        {
            if (string.IsNullOrWhiteSpace(path) || !path.StartsWith("Assets/", StringComparison.Ordinal) || path.Contains("\\") || path.Split('/').Contains(".."))
                throw new InvalidOperationException("generated_root must be a safe forward-slash path below Assets/.");
        }

        internal static string AssetPathToFullPath(string assetPath)
        {
            ValidateAssetPath(assetPath);
            var projectRoot = Directory.GetParent(Application.dataPath)?.FullName ?? throw new InvalidOperationException("Could not resolve the Unity project root.");
            return Path.Combine(projectRoot, assetPath.Replace('/', Path.DirectorySeparatorChar));
        }

        internal static void EnsureAssetFolder(string assetPath)
        {
            ValidateAssetPath(assetPath);
            var parts = assetPath.Split('/');
            var current = parts[0];
            for (var index = 1; index < parts.Length; index++)
            {
                var next = $"{current}/{parts[index]}";
                if (!AssetDatabase.IsValidFolder(next))
                    AssetDatabase.CreateFolder(current, parts[index]);
                current = next;
            }
        }

        private static void CopyToAsset(string sourcePath, string destinationAssetPath)
        {
            if (!File.Exists(sourcePath))
                throw new FileNotFoundException("Tileset image was not found.", sourcePath);
            var destinationFullPath = AssetPathToFullPath(destinationAssetPath);
            Directory.CreateDirectory(Path.GetDirectoryName(destinationFullPath) ?? throw new InvalidOperationException("Tileset destination has no parent."));
            File.Copy(sourcePath, destinationFullPath, true);
            AssetDatabase.ImportAsset(destinationAssetPath, ImportAssetOptions.ForceSynchronousImport | ImportAssetOptions.ForceUpdate);
        }

        private static void ConfigureAndSliceTexture(string assetPath, BundleManifest manifest, TileSlice[] slices)
        {
            var importer = AssetImporter.GetAtPath(assetPath) as TextureImporter ?? throw new InvalidOperationException($"TextureImporter was not found for {assetPath}.");
            importer.textureType = TextureImporterType.Sprite;
            importer.spriteImportMode = SpriteImportMode.Multiple;
            importer.spritePixelsPerUnit = manifest.pixels_per_unit;
            importer.mipmapEnabled = false;
            importer.alphaIsTransparency = true;
            importer.wrapMode = TextureWrapMode.Clamp;
            importer.filterMode = string.Equals(manifest.filter_mode, "bilinear", StringComparison.OrdinalIgnoreCase) ? FilterMode.Bilinear : FilterMode.Point;
            importer.textureCompression = TextureImporterCompression.Uncompressed;
            importer.SaveAndReimport();

            var factory = new SpriteDataProviderFactories();
            factory.Init();
            var dataProvider = factory.GetSpriteEditorDataProviderFromObject(importer) ?? throw new InvalidOperationException("2D Sprite Editor data provider is unavailable. Install com.unity.2d.sprite.");
            dataProvider.InitSpriteEditorDataProvider();
            var existingIds = dataProvider.GetSpriteRects().ToDictionary(item => item.name, item => item.spriteID, StringComparer.Ordinal);
            var spriteRects = slices.Select(slice => new SpriteRect
            {
                name = slice.id,
                rect = new Rect(slice.rect.x, slice.rect.y, slice.rect.width, slice.rect.height),
                alignment = SpriteAlignment.Center,
                pivot = new Vector2(0.5f, 0.5f),
                border = Vector4.zero,
                spriteID = existingIds.TryGetValue(slice.id, out var existingId) ? existingId : UnityEditor.GUID.Generate(),
            }).ToArray();
            dataProvider.SetSpriteRects(spriteRects);
            var names = dataProvider.GetDataProvider<ISpriteNameFileIdDataProvider>() ?? throw new InvalidOperationException("Sprite name/file ID provider is unavailable.");
            names.SetNameFileIdPairs(spriteRects.Select(item => new SpriteNameFileIdPair(item.name, item.spriteID)));
            dataProvider.Apply();
            importer.SaveAndReimport();
        }

        private static Dictionary<string, Tile> CreateOrUpdateTiles(string tileFolder, TileSlice[] slices, IReadOnlyDictionary<string, Sprite> sprites)
        {
            var result = new Dictionary<string, Tile>(StringComparer.Ordinal);
            foreach (var slice in slices)
            {
                if (!sprites.TryGetValue(slice.id, out var sprite))
                    throw new InvalidOperationException($"Imported Sprite '{slice.id}' was not found.");
                var path = $"{tileFolder}/{slice.id}.asset";
                var tile = AssetDatabase.LoadAssetAtPath<Tile>(path);
                if (tile == null)
                {
                    tile = ScriptableObject.CreateInstance<Tile>();
                    AssetDatabase.CreateAsset(tile, path);
                }
                tile.name = slice.id;
                tile.sprite = sprite;
                tile.colliderType = ParseColliderType(slice.collider_type);
                tile.color = Color.white;
                tile.transform = Matrix4x4.identity;
                tile.flags = TileFlags.LockColor | TileFlags.LockTransform;
                EditorUtility.SetDirty(tile);
                result.Add(slice.id, tile);
            }
            return result;
        }

        private static Tile.ColliderType ParseColliderType(string value)
        {
            switch (value)
            {
                case "grid": return Tile.ColliderType.Grid;
                case "sprite": return Tile.ColliderType.Sprite;
                default: return Tile.ColliderType.None;
            }
        }

        private static string CreateOrUpdatePalette(string folder, string paletteName, TileSlice[] slices, IReadOnlyDictionary<string, Tile> tiles)
        {
            var path = $"{folder}/{paletteName}.prefab";
            if (AssetDatabase.LoadAssetAtPath<GameObject>(path) == null)
            {
                GridPaletteUtility.CreateNewPalette(folder, paletteName, GridLayout.CellLayout.Rectangle, GridPalette.CellSizing.Manual, Vector3.one, GridLayout.CellSwizzle.XYZ);
            }
            if (AssetDatabase.LoadAssetAtPath<GameObject>(path) == null)
                throw new InvalidOperationException($"Unity did not create the Tile Palette at '{path}'.");

            var root = PrefabUtility.LoadPrefabContents(path);
            try
            {
                var tilemap = root.GetComponentInChildren<Tilemap>(true) ?? throw new InvalidOperationException("The Tile Palette prefab has no Tilemap.");
                tilemap.ClearAllTiles();
                foreach (var slice in slices)
                    tilemap.SetTile(new Vector3Int(slice.palette.x, slice.palette.y, 0), tiles[slice.id]);
                tilemap.CompressBounds();
                PrefabUtility.SaveAsPrefabAsset(root, path);
            }
            finally
            {
                PrefabUtility.UnloadPrefabContents(root);
            }
            return path;
        }

        private static string CreateOrUpdateTilemapPrefab(string folder, string prefabName, PlacementLayer[] layers, IReadOnlyDictionary<string, Tile> tiles)
        {
            var path = $"{folder}/{prefabName}.prefab";
            var root = new GameObject(prefabName);
            root.AddComponent<Grid>();
            try
            {
                foreach (var layer in layers.OrderBy(item => item.sorting_order))
                {
                    var child = new GameObject(layer.id);
                    child.transform.SetParent(root.transform, false);
                    var tilemap = child.AddComponent<Tilemap>();
                    var renderer = child.AddComponent<TilemapRenderer>();
                    renderer.sortingOrder = layer.sorting_order;
                    foreach (var item in layer.placements)
                        tilemap.SetTile(new Vector3Int(item.x, item.y, 0), tiles[item.tile_id]);
                    tilemap.CompressBounds();
                    if (layer.has_collider)
                        child.AddComponent<TilemapCollider2D>();
                }
                PrefabUtility.SaveAsPrefabAsset(root, path);
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(root);
            }
            return path;
        }
    }
}
