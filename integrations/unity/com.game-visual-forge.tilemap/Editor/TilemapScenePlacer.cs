using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace GameVisualForge.Unity
{
    internal static class TilemapScenePlacer
    {
        internal static ScenePlacementResult PlaceOrUpdate(string prefabAssetPath)
        {
            var scene = SceneManager.GetActiveScene();
            var existing = scene.GetRootGameObjects().FirstOrDefault(root => PrefabUtility.GetPrefabAssetPathOfNearestInstanceRoot(root) == prefabAssetPath);
            if (existing != null)
            {
                EditorSceneManager.MarkSceneDirty(scene);
                return new ScenePlacementResult("updated", existing.name, scene.path, true);
            }
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(prefabAssetPath) ?? throw new System.InvalidOperationException("Tilemap Prefab was not found.");
            var instance = PrefabUtility.InstantiatePrefab(prefab, scene) as GameObject ?? throw new System.InvalidOperationException("Tilemap Prefab could not be instantiated.");
            Undo.RegisterCreatedObjectUndo(instance, "Place Game Visual Forge Tilemap");
            EditorSceneManager.MarkSceneDirty(scene);
            return new ScenePlacementResult("placed", instance.name, scene.path, true);
        }
    }
}
