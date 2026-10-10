import unittest
from tests._bootstrap import ROOT  # noqa: F401
from tests.test_music_contract import music_request
from game_visual_forge.contracts.music import build_music_prompt_package
from game_visual_forge.contracts.music_provider import MusicProvider
from game_visual_forge.providers.comfy_music3 import inspect_comfy_music3_workflow, bind_comfy_music3_generation


def graph(**changes):
    value = {
        "nodes": [
            {"id": "caption", "class_type": "MiniMaxMusic3TextEncode", "inputs": {"caption": "old", "lyrics": "old", "seed": 1, "max_duration": 180}},
            {"id": "latent", "class_type": "EmptyMiniMaxMusic3LatentAudio", "inputs": {"duration": 180}},
            {"id": "sampler", "class_type": "KSampler", "inputs": {"seed": 1}},
            {"id": "decode", "class_type": "VAEDecodeTiled", "inputs": {}},
            {"id": "save", "class_type": "SaveAudioAdvanced", "inputs": {"format": "wav"}},
        ],
        "models": ["minimax_music3_dit_fp16.safetensors", "minimax_music3_text_encoder_pruned_int8_convrot.safetensors", "minimax_music3_dav.safetensors"],
        "subgraphs": [],
    }
    value.update(changes)
    return value


class ComfyMusic3Tests(unittest.TestCase):
    def test_valid_local_workflow_is_ready(self):
        report = inspect_comfy_music3_workflow(graph(), {"MiniMaxMusic3TextEncode": {}, "EmptyMiniMaxMusic3LatentAudio": {}})
        self.assertTrue(report.ready)
        self.assertTrue(report.local_only)
        request = music_request()
        bound = bind_comfy_music3_generation(request, build_music_prompt_package(request, MusicProvider.COMFYUI_MUSIC3, "A gentle track"), report, seed=42)
        self.assertEqual(bound["caption"]["inputs"]["seed"], 42)
        self.assertEqual(bound["sampler"]["inputs"]["seed"], 42)
        self.assertEqual(bound["caption"]["inputs"]["lyrics"], "[instrumental]")

    def test_nested_api_node_is_not_local(self):
        value = graph(subgraphs=[{"nodes": [{"class_type": "KlingVideoApi"}]}])
        report = inspect_comfy_music3_workflow(value, {})
        self.assertFalse(report.local_only)
        self.assertIn("API", " ".join(report.errors + report.warnings))

    def test_unknown_class_missing_model_or_outputs_not_ready(self):
        cases = [
            graph(nodes=graph()["nodes"] + [{"id": "x", "class_type": "MysteryNode", "inputs": {}}]),
            graph(models=[]),
            graph(nodes=[node for node in graph()["nodes"] if node["id"] != "decode"]),
            graph(nodes=[node for node in graph()["nodes"] if node["id"] != "save"]),
            graph(nodes=[node for node in graph()["nodes"] if node["id"] != "sampler"]),
        ]
        for value in cases:
            with self.subTest(value=value):
                self.assertFalse(inspect_comfy_music3_workflow(value, {}).ready)


if __name__ == "__main__":
    unittest.main()
