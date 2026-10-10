from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from game_visual_forge.contracts.music import MusicRequest, MusicPromptPackage
from game_visual_forge.contracts.music_provider import MusicWorkflowReport
from game_visual_forge.contracts.music import music_hash


_KNOWN = {"MiniMaxMusic3TextEncode", "EmptyMiniMaxMusic3LatentAudio", "KSampler", "VAEDecodeTiled", "VAEDecode", "SaveAudioAdvanced", "CheckpointLoaderSimple", "VAELoader", "CLIPLoader", "UNETLoader", "ModelSamplingAuraFlow"}
_MODEL_MARKERS = ("minimax_music3_dit", "minimax_music3_text_encoder", "minimax_music3_dav")


def _nodes(value: Mapping[str, Any]):
    if isinstance(value.get("nodes"), list):
        return [node for node in value["nodes"] if isinstance(node, dict)]
    if isinstance(value.get("nodes"), dict):
        return [dict(node, id=str(node_id)) for node_id, node in value["nodes"].items() if isinstance(node, dict)]
    return []


def _walk_subgraphs(value):
    result = []
    for subgraph in value.get("subgraphs", []) if isinstance(value, dict) else []:
        if isinstance(subgraph, dict):
            result.extend(_nodes(subgraph))
            result.extend(_walk_subgraphs(subgraph))
    return result


def inspect_comfy_music3_workflow(workflow: Mapping[str, Any], object_info: Mapping[str, Any]) -> MusicWorkflowReport:
    nodes = _nodes(workflow)
    all_nodes = nodes + _walk_subgraphs(workflow)
    types = tuple(str(node.get("class_type", node.get("type", ""))) for node in all_nodes)
    models = tuple(str(item) for item in workflow.get("models", ()) if isinstance(item, (str, int, float)))
    errors: list[str] = []
    warnings: list[str] = []
    unknown = [item for item in types if item not in _KNOWN and item]
    api = [item for item in types if "api" in item.lower() or "cloud" in item.lower()]
    if unknown:
        errors.append("unknown node category: " + ", ".join(sorted(set(unknown))))
    if api:
        errors.append("API/cloud node detected: " + ", ".join(sorted(set(api))))
    required = {"MiniMaxMusic3TextEncode", "EmptyMiniMaxMusic3LatentAudio", "SaveAudioAdvanced"}
    missing = required.difference(types)
    if missing:
        errors.append("missing required node: " + ", ".join(sorted(missing)))
    if not any(item in types for item in ("VAEDecodeTiled", "VAEDecode")):
        errors.append("missing audio decode node")
    if not any("wav" in str(node.get("inputs", {}).get("format", "")).lower() for node in all_nodes if str(node.get("class_type")) == "SaveAudioAdvanced"):
        errors.append("audio save node is not configured for WAV")
    if not models or not all(any(marker in model.lower() for model in models) for marker in _MODEL_MARKERS):
        errors.append("required MiniMax Music 3 model files are missing")
    text_nodes = [node for node in all_nodes if node.get("class_type") == "MiniMaxMusic3TextEncode"]
    sampler_nodes = [node for node in all_nodes if node.get("class_type") == "KSampler"]
    if not text_nodes or not any("seed" in node.get("inputs", {}) for node in text_nodes) or not sampler_nodes or not any("seed" in node.get("inputs", {}) for node in sampler_nodes):
        errors.append("caption and sampler seeds are not both bound")
    local_only = not api and not unknown
    spends = bool(workflow.get("spends_credits", False)) or not local_only
    ready = not errors and local_only
    if object_info and "MiniMaxMusic3TextEncode" not in object_info:
        warnings.append("object info does not expose the observed Music 3 text encoder")
    return MusicWorkflowReport(music_hash(workflow), tuple(sorted(set(types))), models, local_only, spends, tuple(str(item) for item in workflow.get("slots", ())), ready, tuple(errors), tuple(warnings))


def bind_comfy_music3_generation(request: MusicRequest, prompt: MusicPromptPackage, workflow_report: MusicWorkflowReport, *, seed: int):
    if not workflow_report.ready:
        raise ValueError("workflow report is not ready: " + "; ".join(workflow_report.errors))
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise TypeError("seed must be an integer")
    # The report is deliberately immutable; callers pass a fresh workflow copy and bind only known IDs.
    bound = {"caption": {"class_type": "MiniMaxMusic3TextEncode", "inputs": {"caption": prompt.caption, "lyrics": prompt.lyrics or "", "seed": seed, "max_duration": request.target_duration_seconds}}, "sampler": {"class_type": "KSampler", "inputs": {"seed": seed}}, "latent": {"class_type": "EmptyMiniMaxMusic3LatentAudio", "inputs": {"duration": request.target_duration_seconds}}, "workflow_sha256": workflow_report.workflow_sha256}
    return bound
