using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using UnityEditor;
using UnityEngine;

namespace GameVisualForge.Unity
{
    public static class AudioBundleImporter
    {
        [MenuItem("Tools/Game Visual Forge/Import Audio Bundle...")]
        private static void ImportFromMenu()
        {
            var manifestPath = EditorUtility.OpenFilePanel("Import Game Visual Forge Audio Bundle", "", "json");
            if (string.IsNullOrEmpty(manifestPath)) return;
            try
            {
                var result = ImportBundle(manifestPath);
                EditorUtility.DisplayDialog("Game Visual Forge", $"Imported {result.asset_id}\n{result.audio_clip_path}", "OK");
            }
            catch (Exception exception)
            {
                Debug.LogException(exception);
                EditorUtility.DisplayDialog("Game Visual Forge audio import failed", exception.Message, "OK");
            }
        }

        public static string ImportBundleForAutomation(string manifestPath)
        {
            return JsonUtility.ToJson(ImportBundle(manifestPath));
        }

        public static AudioImportResult ImportBundle(string manifestPath)
        {
            var fullManifestPath = ResolveInputPath(manifestPath);
            var manifest = ReadJson<AudioBundleManifest>(fullManifestPath);
            ValidateManifest(manifest);
            var bundleDirectory = Path.GetDirectoryName(fullManifestPath);
            var sourcePath = ResolveBundlePath(bundleDirectory, manifest.wav_path);
            var sourceHash = ComputeSHA256(sourcePath);
            if (!string.Equals(sourceHash, manifest.sha256, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("Audio bundle SHA-256 does not match the manifest.");

            var generatedRoot = $"Assets/GameVisualForgeAudio/{manifest.asset_id}";
            var assetPath = $"{generatedRoot}/{manifest.asset_id}.wav";
            var reportRoot = generatedRoot;
            var existingGuid = AssetDatabase.AssetPathToGUID(assetPath);
            var hadExisting = !string.IsNullOrEmpty(existingGuid);
            EnsureAssetFolder(generatedRoot);
            File.Copy(sourcePath, ToProjectFullPath(assetPath), true);
            AssetDatabase.ImportAsset(assetPath, ImportAssetOptions.ForceUpdate);
            ConfigureImporter(assetPath, manifest.importer);
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            var clip = AssetDatabase.LoadAssetAtPath<AudioClip>(assetPath);
            if (clip == null) throw new InvalidOperationException("Unity did not import the WAV as an AudioClip.");
            var result = new AudioImportResult
            {
                asset_id = manifest.asset_id,
                generated_root = generatedRoot,
                audio_clip_path = assetPath,
                guid = AssetDatabase.AssetPathToGUID(assetPath),
                frequency = clip.frequency,
                channels = clip.channels,
                duration = clip.length,
                profile = manifest.profile,
                had_existing_asset = hadExisting,
                guid_stable = !hadExisting || string.Equals(existingGuid, AssetDatabase.AssetPathToGUID(assetPath), StringComparison.Ordinal),
                status = "passed",
                scene_action = "unchanged"
            };
            result.report_path = AudioImportReportWriter.Write(reportRoot, result);
            return result;
        }

        public static string ComputeSHA256(string path)
        {
            using (var sha = SHA256.Create())
            using (var stream = File.OpenRead(path))
            {
                return string.Concat(sha.ComputeHash(stream).Select(value => value.ToString("x2")));
            }
        }

        private static void ConfigureImporter(string assetPath, ImporterSettings settings)
        {
            var importer = AssetImporter.GetAtPath(assetPath) as AudioImporter;
            if (importer == null) throw new InvalidOperationException("AudioImporter was not created.");
            settings ??= new ImporterSettings { load_type = "DecompressOnLoad", compression_format = "PCM", preload_audio_data = true };
            importer.forceToMono = settings.force_to_mono;
            importer.loadInBackground = settings.load_in_background;
            importer.preloadAudioData = settings.preload_audio_data;
            var sample = importer.defaultSampleSettings;
            sample.loadType = ParseLoadType(settings.load_type);
            sample.compressionFormat = ParseCompressionFormat(settings.compression_format);
            if (settings.quality > 0) sample.quality = settings.quality;
            importer.defaultSampleSettings = sample;
            importer.SaveAndReimport();
        }

        private static AudioClipLoadType ParseLoadType(string value)
        {
            return value == "Streaming" ? AudioClipLoadType.Streaming : value == "CompressedInMemory" ? AudioClipLoadType.CompressedInMemory : AudioClipLoadType.DecompressOnLoad;
        }

        private static AudioCompressionFormat ParseCompressionFormat(string value)
        {
            return value == "Vorbis" ? AudioCompressionFormat.Vorbis : value == "ADPCM" ? AudioCompressionFormat.ADPCM : AudioCompressionFormat.PCM;
        }

        private static void ValidateManifest(AudioBundleManifest manifest)
        {
            if (manifest == null || manifest.schema_version != 1 || string.IsNullOrWhiteSpace(manifest.asset_id) || string.IsNullOrWhiteSpace(manifest.wav_path) || string.IsNullOrWhiteSpace(manifest.sha256))
                throw new InvalidOperationException("Audio manifest is missing required schema_version 1 fields.");
            if (manifest.asset_id.Any(character => !(char.IsLetterOrDigit(character) || character == '-' || character == '_')))
                throw new InvalidOperationException("Audio asset_id contains invalid path characters.");
            _ = ResolveBundlePath(".", manifest.wav_path);
        }

        private static string ResolveInputPath(string path)
        {
            if (Path.IsPathRooted(path)) return Path.GetFullPath(path);
            return ToProjectFullPath(path);
        }

        private static string ResolveBundlePath(string directory, string relativePath)
        {
            if (Path.IsPathRooted(relativePath)) throw new InvalidOperationException("Audio bundle paths must be relative.");
            var combined = Path.GetFullPath(Path.Combine(directory, relativePath));
            var root = Path.GetFullPath(directory).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
            if (!combined.StartsWith(root, StringComparison.OrdinalIgnoreCase)) throw new InvalidOperationException("Audio bundle path escapes its directory.");
            return combined;
        }

        private static string ToProjectFullPath(string assetPath)
        {
            var projectRoot = Directory.GetParent(Application.dataPath).FullName;
            return Path.GetFullPath(Path.Combine(projectRoot, assetPath.Replace('/', Path.DirectorySeparatorChar)));
        }

        private static void EnsureAssetFolder(string assetPath)
        {
            var fullPath = ToProjectFullPath(assetPath);
            Directory.CreateDirectory(fullPath);
            AssetDatabase.Refresh();
        }

        private static T ReadJson<T>(string path)
        {
            if (!File.Exists(path)) throw new FileNotFoundException("Audio bundle manifest was not found.", path);
            return JsonUtility.FromJson<T>(File.ReadAllText(path, Encoding.UTF8));
        }
    }
}
