using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using UnityEditor;
using UnityEngine;

namespace GameVisualForge.Unity
{
    internal static class TilemapImportReportWriter
    {
        [Serializable]
        private sealed class ManifestQualityFields
        {
            public string quality_report;
            public string quality_report_sha256;
        }

        internal static string Write(string manifestFullPath, TilemapBundleImporter.ImportResult result, int atlasPageCount, ImportMode mode)
        {
            var manifestDirectory = Path.GetDirectoryName(manifestFullPath) ?? throw new InvalidOperationException("Manifest has no parent directory.");
            var fields = JsonUtility.FromJson<ManifestQualityFields>(File.ReadAllText(manifestFullPath));
            var reportPath = string.IsNullOrWhiteSpace(fields.quality_report) ? null : Path.Combine(manifestDirectory, fields.quality_report);
            var reportHash = reportPath != null && File.Exists(reportPath) ? ComputeSha256(reportPath) : null;
            if (!string.IsNullOrWhiteSpace(fields.quality_report_sha256) && !string.Equals(fields.quality_report_sha256, reportHash, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("Python quality report SHA-256 does not match the Unity manifest.");

            var report = new UnityImportReport
            {
                asset_id = result.asset_id,
                generated_root = result.generated_root,
                python_quality_report = reportPath == null ? null : fields.quality_report,
                python_quality_report_sha256 = reportHash,
                had_existing_assets = result.had_existing_assets,
                resource_guids_stable = result.resource_guids_stable,
                atlas_page_paths = result.tileset_assets ?? Array.Empty<string>(),
                tile_paths = result.tile_assets ?? Array.Empty<string>(),
                atlas_page_count = atlasPageCount,
                sprite_count = result.tile_count,
                tile_count = result.tile_count,
                layer_count = result.layer_count,
                palette_path = result.palette_prefab,
                prefab_path = result.tilemap_prefab,
                building_entrances_asset = result.building_entrances_asset,
                scene_action = result.scene_action,
                scene_path = result.scene_path,
                scene_dirty = result.scene_dirty,
                objects_manifest = result.objects_manifest,
                collision_manifest = result.collision_manifest,
                object_prefab_paths = result.object_prefabs ?? Array.Empty<string>(),
                object_count = result.object_count,
                foundation = result.foundation,
                foundation_recomposition = result.foundation_recomposition,
                scene_acceptance_report = result.scene_acceptance_report,
                scene_acceptance_status = result.scene_acceptance_status,
            };
            var reportsFolder = $"{result.generated_root}/Reports";
            TilemapBundleImporter.EnsureAssetFolder(reportsFolder);
            var assetPath = $"{reportsFolder}/unity-import-report.json";
            File.WriteAllText(TilemapBundleImporter.AssetPathToFullPath(assetPath), JsonUtility.ToJson(report, true));
            AssetDatabase.ImportAsset(assetPath, ImportAssetOptions.ForceUpdate);
            return assetPath;
        }

        internal static string ComputeSha256(string path)
        {
            using (var stream = File.OpenRead(path))
            using (var algorithm = SHA256.Create())
                return string.Concat(algorithm.ComputeHash(stream).Select(value => value.ToString("x2")));
        }
    }
}
