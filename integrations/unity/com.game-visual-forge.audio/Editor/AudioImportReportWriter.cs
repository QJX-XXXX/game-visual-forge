using System.IO;
using System.Text;
using UnityEngine;

namespace GameVisualForge.Unity
{
    internal static class AudioImportReportWriter
    {
        public static string Write(string generatedRoot, AudioImportResult result)
        {
            var reportPath = $"{generatedRoot}/Reports/unity-import-report.json";
            var fullPath = Path.Combine(Directory.GetParent(Application.dataPath).FullName, reportPath);
            Directory.CreateDirectory(Path.GetDirectoryName(fullPath));
            File.WriteAllText(fullPath, JsonUtility.ToJson(result, true), new UTF8Encoding(false));
            return reportPath;
        }
    }
}
