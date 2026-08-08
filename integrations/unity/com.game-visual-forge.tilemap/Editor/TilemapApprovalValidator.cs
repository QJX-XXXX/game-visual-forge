using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using UnityEngine;

namespace GameVisualForge.Unity
{
    internal static class TilemapApprovalValidator
    {
        [Serializable]
        private sealed class ApprovalRecord { public int schema_version; public string gate; public string status; public string reviewer; public ApprovalArtifact[] artifacts; }
        [Serializable]
        private sealed class ApprovalArtifact { public string role; public string path; public string sha256; }

        internal static void Validate(string manifestFullPath, BundleManifest manifest)
        {
            var bundleDirectory = Path.GetDirectoryName(manifestFullPath) ?? throw new InvalidOperationException("Bundle manifest has no parent directory.");
            var rejection = Path.Combine(bundleDirectory, "rejection.json");
            if (File.Exists(rejection))
                throw new InvalidOperationException("Rejected tilemap runs cannot be imported.");
            if (!string.Equals(manifest.approval_workflow, "two_gate", StringComparison.Ordinal))
                return;
            ValidateApproval(bundleDirectory, manifest.style_approval, manifest.style_approval_sha256, "style-sample", new[] { "style-sample", "art-direction" });
            ValidateApproval(bundleDirectory, manifest.assembled_approval, manifest.assembled_approval_sha256, "assembled-map", new[] { "review-sheet", "tilemap-preview", "gameplay-crop", "tilemap-placement", "tilemap-objects", "tilemap-collision", "asset-set" });
        }

        private static void ValidateApproval(string bundleDirectory, string relativePath, string expectedHash, string gate, string[] roles)
        {
            if (string.IsNullOrWhiteSpace(relativePath) || string.IsNullOrWhiteSpace(expectedHash))
                throw new InvalidOperationException($"Two-gate bundle is missing {gate} approval.");
            var path = ResolveInsideBundle(bundleDirectory, relativePath);
            if (!File.Exists(path) || !string.Equals(ComputeSha256(path), expectedHash, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException($"{gate} approval hash does not match the Unity manifest.");
            var record = JsonUtility.FromJson<ApprovalRecord>(File.ReadAllText(path));
            if (record == null || record.schema_version != 1 || record.gate != gate || record.status != "approved" || record.reviewer != "user" || record.artifacts == null || !record.artifacts.Select(item => item.role).SequenceEqual(roles))
                throw new InvalidOperationException($"{gate} approval record is not an exact user approval.");
            foreach (var artifact in record.artifacts)
            {
                var artifactPath = ResolveInsideBundle(bundleDirectory, artifact.path);
                if (!File.Exists(artifactPath) || !string.Equals(ComputeSha256(artifactPath), artifact.sha256, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException($"{gate} approval artifact hash mismatch for {artifact.role}.");
            }
        }

        private static string ResolveInsideBundle(string bundleDirectory, string relativePath)
        {
            if (string.IsNullOrWhiteSpace(relativePath) || Path.IsPathRooted(relativePath))
                throw new InvalidOperationException("Approval paths must be relative files.");
            var root = Path.GetFullPath(bundleDirectory).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) + Path.DirectorySeparatorChar;
            var resolved = Path.GetFullPath(Path.Combine(bundleDirectory, relativePath));
            if (!resolved.StartsWith(root, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("Approval paths must remain inside the bundle directory.");
            return resolved;
        }

        private static string ComputeSha256(string path)
        {
            using (var stream = File.OpenRead(path))
            using (var algorithm = SHA256.Create())
                return string.Concat(algorithm.ComputeHash(stream).Select(value => value.ToString("x2")));
        }
    }
}
