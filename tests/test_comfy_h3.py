from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tests._bootstrap import ROOT
from game_visual_forge.contracts.comfy_h3 import ComfyH3GenerationRecord
from game_visual_forge.processing.comfy_h3_workflow import inspect_comfy_h3_workflow, load_and_inspect_comfy_h3_workflow


def workflow(*, last_linked: bool = True, randomized: bool = False, length: int = 124, api: bool = False) -> dict:
    nodes = [
        {
            "id": 1,
            "type": "LoadImage",
            "widgets_values": ["ready.png", "image"],
            "outputs": [{"name": "IMAGE", "links": [10, 11]}],
        },
        {
            "id": 2,
            "type": "RandomNoise",
            "widgets_values": [123456, "randomize" if randomized else "fixed"],
        },
        {
            "id": 3,
            "type": "MiniMaxH3ImageToVideo",
            "inputs": [
                {"name": "first_frame", "link": 10},
                {"name": "last_frame", "link": 11 if last_linked else None},
            ],
            "widgets_values": ["prompt", 640, 640, length],
        },
    ]
    links = [[10, 1, 0, 3, 2], [11, 1, 0, 3, 3]] if last_linked else [[10, 1, 0, 3, 2]]
    if api:
        nodes.append({"id": 4, "type": "PartnerAPIVideo", "widgets_values": []})
    return {"nodes": nodes, "links": links}


class ComfyH3WorkflowTests(unittest.TestCase):
    def test_accepts_local_fixed_seed_fl2va_workflow(self) -> None:
        report = inspect_comfy_h3_workflow(workflow())
        self.assertTrue(report.ok)
        self.assertTrue(report.first_frame_connected)
        self.assertTrue(report.last_frame_connected)
        self.assertTrue(report.same_keyframe_source)
        self.assertEqual(report.seed_mode, "fixed")
        self.assertEqual(report.length, 124)
        self.assertTrue(report.local_only)
        self.assertEqual(report.errors, ())

    def test_rejects_disconnected_last_frame(self) -> None:
        report = inspect_comfy_h3_workflow(workflow(last_linked=False))
        self.assertFalse(report.ok)
        self.assertIn("last_frame-not-connected", report.errors)

    def test_rejects_randomized_seed(self) -> None:
        report = inspect_comfy_h3_workflow(workflow(randomized=True))
        self.assertFalse(report.ok)
        self.assertIn("seed-not-fixed", report.errors)

    def test_rejects_invalid_h3_length(self) -> None:
        report = inspect_comfy_h3_workflow(workflow(length=73))
        self.assertFalse(report.ok)
        self.assertIn("invalid-h3-length", report.errors)

    def test_rejects_api_node(self) -> None:
        report = inspect_comfy_h3_workflow(workflow(api=True))
        self.assertFalse(report.ok)
        self.assertIn("non-local-node", report.errors)
        self.assertFalse(report.local_only)

    def test_load_and_inspect_hashes_workflow_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workflow.json"
            path.write_text(json.dumps(workflow(), separators=(",", ":")), encoding="utf-8")
            report = load_and_inspect_comfy_h3_workflow(path)
            self.assertEqual(report.workflow_sha256, hashlib.sha256(path.read_bytes()).hexdigest())


class ComfyH3GenerationRecordTests(unittest.TestCase):
    def test_record_round_trips_without_secrets(self) -> None:
        digest = "a" * 64
        record = ComfyH3GenerationRecord(
            schema_version=1,
            request_fingerprint=digest,
            workflow_sha256=digest,
            prompt_sha256=digest,
            reference_paths=("inputs/ready.png", "inputs/ready.png"),
            reference_sha256=(digest, digest),
            model="minimax_h3_fl2va_pruned_int8_convrot.safetensors",
            seed=123,
            steps=20,
            prompt_id="prompt-123",
            terminal_status="completed",
            output_path="outputs/ready.mp4",
            output_sha256=digest,
        )
        payload = record.to_dict()
        self.assertEqual(ComfyH3GenerationRecord.from_dict(payload), record)
        self.assertNotIn("password", json.dumps(payload))
        self.assertNotIn("Authorization", json.dumps(payload))

    def test_record_rejects_malformed_digest(self) -> None:
        digest = "a" * 64
        with self.assertRaisesRegex(ValueError, "workflow_sha256"):
            ComfyH3GenerationRecord(
                schema_version=1,
                request_fingerprint=digest,
                workflow_sha256="bad",
                prompt_sha256=digest,
                reference_paths=(),
                reference_sha256=(),
                model="h3",
                seed=1,
                steps=20,
            )


if __name__ == "__main__":
    unittest.main()
