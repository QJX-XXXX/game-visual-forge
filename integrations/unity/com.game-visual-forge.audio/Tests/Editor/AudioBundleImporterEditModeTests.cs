using System.IO;
using System.Security.Cryptography;
using System.Text;
using NUnit.Framework;
using UnityEditor;
using UnityEngine;

namespace GameVisualForge.Unity.Tests
{
    public sealed class AudioBundleImporterEditModeTests
    {
        [Test]
        public void ComputeSHA256IsDeterministic()
        {
            var path = Path.Combine(Application.dataPath, "audio-hash-fixture.txt");
            File.WriteAllText(path, "forge-audio", new UTF8Encoding(false));
            try
            {
                Assert.AreEqual(AudioBundleImporter.ComputeSHA256(path), AudioBundleImporter.ComputeSHA256(path));
            }
            finally
            {
                File.Delete(path);
                AssetDatabase.Refresh();
            }
        }

        [Test]
        public void ImporterDoesNotExposeScenePlacementApi()
        {
            var method = typeof(AudioBundleImporter).GetMethod("ImportAndPlaceBundleForAutomation");
            Assert.IsNull(method);
        }
    }
}
