from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests._bootstrap import ROOT  # noqa: F401
from game_visual_forge.contracts import (
    AssetBrief,
    ArtifactRecord,
    AssetKind,
    AssetManifest,
    SourcePreference,
    dump_json,
    load_json,
)


class AssetContractTests(unittest.TestCase):
    def test_asset_brief_round_trips_as_versioned_json(self) -> None:
        brief = AssetBrief(
            schema_version=1,
            asset_id="hero-run",
            kind=AssetKind.SPRITE,
            prompt="A side-view swordswoman running in place.",
            output_dir="outputs/hero-run",
            source_preference=SourcePreference.AUTO,
            reference_paths=("references/hero.png",),
            canvas_width=1024,
            canvas_height=1024,
            frame_count=8,
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "brief.json"
            dump_json(path, brief.to_dict())
            restored = AssetBrief.from_dict(load_json(path))
        self.assertEqual(restored, brief)

    def test_asset_id_rejects_paths(self) -> None:
        with self.assertRaisesRegex(ValueError, "asset_id"):
            AssetBrief(
                1,
                "../escape",
                AssetKind.SPRITE,
                "prompt",
                "outputs/item",
                SourcePreference.AUTO,
            )

    def test_positive_dimensions_are_enforced(self) -> None:
        with self.assertRaisesRegex(ValueError, "canvas_width"):
            AssetBrief(
                1,
                "item",
                AssetKind.SPRITE,
                "prompt",
                "outputs/item",
                SourcePreference.AUTO,
                canvas_width=0,
            )

    def test_asset_paths_reject_dot_segment_escapes(self) -> None:
        with self.assertRaisesRegex(ValueError, "output_dir"):
            AssetBrief(
                1,
                "item",
                AssetKind.SPRITE,
                "prompt",
                "../escape",
                SourcePreference.AUTO,
            )
        with self.assertRaisesRegex(ValueError, "reference_paths"):
            AssetBrief(
                1,
                "item",
                AssetKind.SPRITE,
                "prompt",
                "outputs/item",
                SourcePreference.AUTO,
                reference_paths=("references/../secret.png",),
            )

    def test_asset_paths_reject_absolute_posix_and_windows_drive_paths(self) -> None:
        for output_dir in ("/abs/path", "C:/abs/path"):
            with self.subTest(field="output_dir", value=output_dir):
                with self.assertRaisesRegex(ValueError, "output_dir"):
                    AssetBrief(
                        1,
                        "item",
                        AssetKind.SPRITE,
                        "prompt",
                        output_dir,
                        SourcePreference.AUTO,
                    )

        for reference_path in ("/abs/path", "C:/abs/path"):
            with self.subTest(field="reference_paths", value=reference_path):
                with self.assertRaisesRegex(ValueError, "reference_paths"):
                    AssetBrief(
                        1,
                        "item",
                        AssetKind.SPRITE,
                        "prompt",
                        "outputs/item",
                        SourcePreference.AUTO,
                        reference_paths=(reference_path,),
                    )

    def test_asset_paths_are_normalized_to_posix(self) -> None:
        brief = AssetBrief(
            schema_version=1,
            asset_id="hero-run",
            kind=AssetKind.SPRITE,
            prompt="A side-view swordswoman running in place.",
            output_dir=r"outputs\hero-run",
            source_preference=SourcePreference.AUTO,
            reference_paths=(r"references\hero.png",),
        )
        self.assertEqual(brief.output_dir, "outputs/hero-run")
        self.assertEqual(brief.reference_paths, ("references/hero.png",))

    def test_manifest_round_trip_keeps_provenance_and_quality(self) -> None:
        manifest = AssetManifest(
            schema_version=1,
            asset_id="hero-run",
            source_type="agent-native",
            provider=None,
            model=None,
            artifacts=(
                ArtifactRecord(
                    role="source",
                    path="outputs/hero-run/source.png",
                    sha256="b" * 64,
                ),
            ),
            processing_steps=("inspect-generated-media",),
            quality_status="passed",
        )
        restored = AssetManifest.from_dict(manifest.to_dict())
        self.assertEqual(restored, manifest)

    def test_manifest_artifact_path_rejects_dot_segments(self) -> None:
        with self.assertRaisesRegex(ValueError, "path"):
            ArtifactRecord(
                role="source",
                path="outputs/hero-run/../escape.png",
                sha256="b" * 64,
            )

    def test_manifest_artifact_path_rejects_absolute_posix_and_windows_drive_paths(self) -> None:
        for artifact_path in ("/abs/path", "C:/abs/path"):
            with self.subTest(value=artifact_path):
                with self.assertRaisesRegex(ValueError, "path"):
                    ArtifactRecord(
                        role="source",
                        path=artifact_path,
                        sha256="b" * 64,
                    )

    def test_dump_json_writes_deterministic_sorted_utf8_object_with_trailing_newline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "payload.json"
            dump_json(path, {"z": "雪", "a": 1})
            payload = path.read_text(encoding="utf-8")
        self.assertEqual(payload, '{\n  "a": 1,\n  "z": "雪"\n}\n')
        self.assertEqual(json.loads(payload), {"a": 1, "z": "雪"})

    def test_load_json_rejects_non_object_documents(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "payload.json"
            path.write_text('["not", "an", "object"]\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "object"):
                load_json(path)


if __name__ == "__main__":
    unittest.main()
