from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

from game_visual_forge.contracts.comfy_h3 import ComfyH3WorkflowReport
from game_visual_forge.contracts.serialization import load_json


_H3_TYPE = "MiniMaxH3ImageToVideo"
_NON_LOCAL_MARKERS = ("api", "cloud", "partner")
_SEED_MODES = {"fixed", "randomize", "increment", "decrement"}


def _node_type(node: Mapping[str, Any]) -> str:
    return str(node.get("type", node.get("class_type", "")))


def _nodes(workflow: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    if isinstance(workflow.get("nodes"), list):
        return tuple(item for item in workflow["nodes"] if isinstance(item, Mapping))
    result = []
    for key, value in workflow.items():
        if isinstance(value, Mapping) and (str(key).isdigit() or "class_type" in value):
            item = dict(value)
            item.setdefault("id", key)
            result.append(item)
    return tuple(result)


def _inputs(node: Mapping[str, Any]) -> dict[str, Any]:
    value = node.get("inputs", {})
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, list):
        return {str(item.get("name")): item for item in value if isinstance(item, Mapping) and item.get("name")}
    return {}


def _connected(value: Any) -> bool:
    if isinstance(value, Mapping):
        return value.get("link") is not None or value.get("node") is not None
    return value is not None


def _link_sources(workflow: Mapping[str, Any]) -> dict[Any, Any]:
    result: dict[Any, Any] = {}
    links = workflow.get("links", [])
    if not isinstance(links, list):
        return result
    for link in links:
        if isinstance(link, (list, tuple)) and len(link) >= 2:
            result[link[0]] = link[1]
    return result


def _source_id(workflow: Mapping[str, Any], value: Any) -> Any:
    if isinstance(value, Mapping):
        if value.get("node") is not None:
            return value.get("node")
        value = value.get("link")
    return _link_sources(workflow).get(value)


def _length(node: Mapping[str, Any]) -> int | None:
    values = _inputs(node)
    candidate = values.get("length")
    if isinstance(candidate, Mapping):
        candidate = candidate.get("value")
    if isinstance(candidate, int) and not isinstance(candidate, bool):
        return candidate
    widgets = node.get("widgets_values", [])
    if isinstance(widgets, list):
        integers = [item for item in widgets if isinstance(item, int) and not isinstance(item, bool)]
        if integers:
            return integers[-1]
    return None


def _seed_mode(nodes: tuple[Mapping[str, Any], ...]) -> str:
    modes: list[str] = []
    for node in nodes:
        values = node.get("widgets_values", [])
        if isinstance(values, list):
            modes.extend(str(item).lower() for item in values if isinstance(item, str) and str(item).lower() in _SEED_MODES)
        inputs = _inputs(node)
        for key in ("control_after_generate", "seed_mode", "mode"):
            value = inputs.get(key)
            if isinstance(value, Mapping):
                value = value.get("value")
            if isinstance(value, str) and value.lower() in _SEED_MODES:
                modes.append(value.lower())
    if "randomize" in modes:
        return "randomize"
    if "fixed" in modes:
        return "fixed"
    return modes[0] if modes else "unknown"


def _valid_h3_length(length: int | None) -> bool:
    return length is not None and length >= 124 and (length - 5) % 17 == 0


def inspect_comfy_h3_workflow(workflow: Mapping[str, Any], *, workflow_sha256: str | None = None) -> ComfyH3WorkflowReport:
    nodes = _nodes(workflow)
    h3_nodes = tuple(node for node in nodes if _node_type(node) == _H3_TYPE)
    first_connected = False
    last_connected = False
    same_source = False
    length = None
    if len(h3_nodes) == 1:
        h3 = h3_nodes[0]
        values = _inputs(h3)
        first = values.get("first_frame")
        last = values.get("last_frame")
        first_connected = _connected(first)
        last_connected = _connected(last)
        first_id = _source_id(workflow, first)
        last_id = _source_id(workflow, last)
        same_source = first_connected and last_connected and first_id is not None and first_id == last_id
        length = _length(h3)
    seed_mode = _seed_mode(nodes)
    local_only = not any(any(marker in _node_type(node).lower() for marker in _NON_LOCAL_MARKERS) for node in nodes)
    errors: list[str] = []
    if len(h3_nodes) != 1:
        errors.append("h3-node-count")
    if not first_connected:
        errors.append("first_frame-not-connected")
    if not last_connected:
        errors.append("last_frame-not-connected")
    if first_connected and last_connected and not same_source:
        errors.append("keyframe-source-mismatch")
    if seed_mode != "fixed":
        errors.append("seed-not-fixed")
    if not _valid_h3_length(length):
        errors.append("invalid-h3-length")
    if not local_only:
        errors.append("non-local-node")
    return ComfyH3WorkflowReport(
        schema_version=1,
        workflow_sha256=workflow_sha256 or ("0" * 64),
        h3_node_count=len(h3_nodes),
        first_frame_connected=first_connected,
        last_frame_connected=last_connected,
        same_keyframe_source=same_source,
        seed_mode=seed_mode,
        length=length,
        local_only=local_only,
        errors=tuple(dict.fromkeys(errors)),
    )


def load_and_inspect_comfy_h3_workflow(path: Path) -> ComfyH3WorkflowReport:
    raw = path.read_bytes()
    import json

    workflow = json.loads(raw.decode("utf-8"))
    if not isinstance(workflow, Mapping):
        raise ValueError("workflow JSON must be an object")
    return inspect_comfy_h3_workflow(workflow, workflow_sha256=hashlib.sha256(raw).hexdigest())
