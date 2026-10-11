from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tests._bootstrap import ROOT  # noqa: F401
from tests.test_normalize_tile_atlas import make_request, native_decision
from game_visual_forge.contracts import SourceType, TileAtlasSourceRecord, TileMapSourceSet
from game_visual_forge.jobs import fingerprint_request
from game_visual_forge.processing.images import ingest_image, sha256_file
from game_visual_forge.processing.tilemap import process_tilemap
from game_visual_forge.processing.tilemap_atlas_normalization import normalize_tilemap_atlases
from game_visual_forge.quality.tilemap import build_tilemap_asset_manifest, validate_tilemap_outputs


class TilemapAtlasNormalizationProvenanceTests(unittest.TestCase):
    def test_process_and_manifest_publish_normalization_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            request = make_request()
            decision = native_decision(request)
            source = root / "generated.png"
            Image.new("RGBA", (1024, 1024), (50, 90, 120, 255)).save(source)
            generated_pages = (("page-01", source), ("page-02", source), ("page-03", source))
            normalization = normalize_tilemap_atlases(root, request, decision, generated_pages, root / "normalized")
            fingerprint = fingerprint_request(request.to_dict())
            page_records = tuple(
                TileAtlasSourceRecord(
                    page.atlas_id,
                    ingest_image(root, root / page.output_path, SourceType.EXISTING_FILE, fingerprint),
                )
                for page in normalization.pages
            )
            source_set = TileMapSourceSet(
                1,
                page_records,
                atlas_normalization_report_path="normalized/atlas-normalization-report.json",
                atlas_normalization_report_sha256=sha256_file(root / "normalized/atlas-normalization-report.json"),
            )

            processing = process_tilemap(root, request, source_set, root / request.output_dir)
            staging = root / processing.staging_dir
            quality = validate_tilemap_outputs(staging, request, source_set, processing)
            manifest = build_tilemap_asset_manifest(staging, request, source_set, processing, quality)

            self.assertTrue((staging / "atlas-normalization-report.json").is_file())
            report_artifacts = [item for item in manifest.artifacts if item.role == "atlas-normalization-report"]
            self.assertEqual(len(report_artifacts), 1)
            self.assertEqual(report_artifacts[0].sha256, sha256_file(staging / "atlas-normalization-report.json"))

    def test_changed_normalization_report_blocks_processing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            request = make_request()
            decision = native_decision(request)
            source = root / "generated.png"
            Image.new("RGBA", (1024, 1024), (50, 90, 120, 255)).save(source)
            normalization = normalize_tilemap_atlases(
                root,
                request,
                decision,
                (("page-01", source), ("page-02", source), ("page-03", source)),
                root / "normalized",
            )
            fingerprint = fingerprint_request(request.to_dict())
            pages = tuple(
                TileAtlasSourceRecord(page.atlas_id, ingest_image(root, root / page.output_path, SourceType.EXISTING_FILE, fingerprint))
                for page in normalization.pages
            )
            report_path = root / "normalized/atlas-normalization-report.json"
            source_set = TileMapSourceSet(
                1,
                pages,
                atlas_normalization_report_path="normalized/atlas-normalization-report.json",
                atlas_normalization_report_sha256=sha256_file(report_path),
            )
            report_path.write_text(report_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

            with self.assertRaisesRegex(Exception, "normalization report hash changed"):
                process_tilemap(root, request, source_set, root / request.output_dir)


if __name__ == "__main__":
    unittest.main()
