from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
