using System;

namespace GameVisualForge.Unity
{
    [Serializable]
    internal sealed class AudioBundleManifest
    {
        public int schema_version;
        public string asset_id;
        public string wav_path;
        public string profile;
        public ImporterSettings importer;
        public string sha256;
    }

    [Serializable]
    internal sealed class ImporterSettings
    {
        public bool force_to_mono;
        public string load_type;
        public string compression_format;
        public bool preload_audio_data;
        public bool load_in_background;
        public float quality;
    }

    [Serializable]
    public sealed class AudioImportResult
    {
        public string asset_id;
        public string generated_root;
        public string audio_clip_path;
        public string report_path;
        public string guid;
        public int frequency;
        public int channels;
        public float duration;
        public string profile;
        public bool had_existing_asset;
        public bool guid_stable;
        public string status;
        public string scene_action;
    }
}
