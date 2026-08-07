using System;

namespace GameVisualForge.Unity
{
    [Serializable]
    internal sealed class AtlasPage
    {
        public string atlas_id;
        public string path;
    }

    [Serializable]
    internal sealed class BundleManifest
    {
        public int schema_version;
        public string asset_id;
        public string engine_target;
        public string tileset;
        public AtlasPage[] tilesets;
        public string slices;
        public string placement;
        public string building_entrances;
        public string quality_report;
        public string quality_report_sha256;
        public string generated_root;
        public int pixels_per_unit;
        public int tile_width;
        public int tile_height;
        public string filter_mode;
        public string palette_name;
        public string prefab_name;
        public string approval_workflow;
        public string style_approval;
        public string style_approval_sha256;
        public string assembled_approval;
        public string assembled_approval_sha256;
        public string objects;
        public string collision;
        public string asset_set;
        public string gameplay_crop;
        public string collision_preview;
    }

    [Serializable]
    internal sealed class SliceManifest
    {
        public int schema_version;
        public TileSlice[] tiles;
    }

    [Serializable]
    internal sealed class TileSlice
    {
        public string id;
        public string atlas_id;
        public RectData rect;
        public PointData palette;
        public string collider_type;
    }

    [Serializable]
    internal sealed class RectData
    {
        public int x;
        public int y;
        public int width;
        public int height;
    }

    [Serializable]
    internal sealed class PointData
    {
        public int x;
        public int y;
    }

    [Serializable]
    internal sealed class PlacementManifest
    {
        public int schema_version;
        public MapSize map_size;
        public PlacementLayer[] layers;
    }

    [Serializable]
    internal sealed class ObjectManifest
    {
        public int schema_version;
        public ObjectAsset[] assets;
        public ObjectPlacement[] placements;
        public ObjectEntrance[] entrances;
    }

    [Serializable]
    internal sealed class ObjectAsset
    {
        public string id;
        public string kind;
        public string path;
        public int pixel_width;
        public int pixel_height;
        public int pixels_per_unit;
        public GridRectData footprint;
        public GridCellData[] collision_cells;
        public GridCellData doorway_cell;
    }

    [Serializable]
    internal sealed class ObjectPlacement
    {
        public string id;
        public string asset_id;
        public int x;
        public int y;
        public int sorting_order;
    }

    [Serializable]
    internal sealed class ObjectEntrance
    {
        public string id;
        public string instance_id;
        public string connection_target;
        public string target_scene_id;
        public string target_spawn_id;
        public GridCellData cell;
    }

    [Serializable]
    internal sealed class GridCellData { public int x; public int y; }

    [Serializable]
    internal sealed class GridRectData { public int x; public int y; public int width; public int height; }

    [Serializable]
    internal sealed class MapSize
    {
        public int width;
        public int height;
    }

    [Serializable]
    internal sealed class PlacementLayer
    {
        public string id;
        public int sorting_order;
        public bool has_collider;
        public Placement[] placements;
    }

    [Serializable]
    internal sealed class Placement
    {
        public int x;
        public int y;
        public string tile_id;
    }

    public static partial class TilemapBundleImporter
    {
        [Serializable]
        public sealed class ImportResult
        {
            public string asset_id;
            public string generated_root;
            public string tileset_asset;
            public string[] tileset_assets;
            public string palette_prefab;
            public string tilemap_prefab;
            public string building_entrances_asset;
            public string[] tile_assets;
            public int tile_count;
            public int layer_count;
            public bool had_existing_assets;
            public bool resource_guids_stable;
            public string scene_action;
            public string scene_path;
            public bool scene_dirty;
            public string unity_import_report;
            public string objects_manifest;
            public string collision_manifest;
            public string[] object_prefabs;
            public int object_count;
        }
    }

    public enum ImportMode
    {
        AssetsOnly,
        ImportAndPlace,
    }

    [Serializable]
    public sealed class ScenePlacementResult
    {
        public string scene_action;
        public string instance_name;
        public string scene_path;
        public bool scene_dirty;
        public string objects_manifest;
        public string collision_manifest;
        public string[] object_prefab_paths;
        public int object_count;

        public ScenePlacementResult(string action, string name, string path, bool dirty)
        {
            scene_action = action;
            instance_name = name;
            scene_path = path;
            scene_dirty = dirty;
        }
    }

    [Serializable]
    public sealed class UnityImportReport
    {
        public int schema_version = 1;
        public string asset_id;
        public string generated_root;
        public string python_quality_report;
        public string python_quality_report_sha256;
        public bool had_existing_assets;
        public bool resource_guids_stable;
        public string[] atlas_page_paths;
        public string[] tile_paths;
        public int atlas_page_count;
        public int sprite_count;
        public int tile_count;
        public int layer_count;
        public string palette_path;
        public string prefab_path;
        public string building_entrances_asset;
        public string scene_action;
        public string scene_path;
        public bool scene_dirty;
    }
}
