using System;

namespace GameVisualForge.Unity
{
    [Serializable]
    internal sealed class AtlasPage
    {
        public string atlas_id;
        public string path;
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
        public int atlas_page_count;
        public int sprite_count;
        public int tile_count;
        public int layer_count;
        public string palette_path;
        public string prefab_path;
        public string scene_action;
        public string scene_path;
        public bool scene_dirty;
    }
}
