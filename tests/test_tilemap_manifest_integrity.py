from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tests._bootstrap import ROOT  # noqa: F401
from game_visual_forge.cli.tilemap import run_tilemap_validate
from game_visual_forge.contracts import JobState, JobStatus, SourceType, load_json
from game_visual_forge.contracts.serialization import dump_json
from game_visual_forge.jobs import fingerprint_request, save_job
from game_visual_forge.processing.images import ingest_image, sha256_file
from game_visual_forge.processing.tilemap import process_tilemap
from game_visual_forge.quality.tilemap import validate_tilemap_outputs
from tests.test_tilemap_contract import make_tilemap_request
from tests.test_tilemap_quality_metrics import bridge_atlas, bridge_request
from game_visual_forge.contracts import BridgeConnectivityRule, BridgeOrientation


class TileMapManifestIntegrityTests(unittest.TestCase):
    def test_missing_building_entrance_artifact_fails_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request = make_tilemap_request()
            source = root / "tileset.png"
            Image.new("RGBA", (32, 32), (45, 140, 65, 255)).save(source)
            record = ingest_image(root, source, SourceType.EXISTING_FILE, "a" * 64)
            result = process_tilemap(root, request, record, root / request.output_dir)
            staging = root / result.staging_dir
            (staging / result.building_entrances_path).unlink()

            report = validate_tilemap_outputs(staging, request, record, result)

            self.assertEqual(report.deterministic_status.value, "failed")
            check = next(item for item in report.deterministic_checks if item.check_id == "building-entrances")
            self.assertEqual(check.status.value, "failed")

    def test_failed_bridge_connectivity_cannot_publish_final_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request = bridge_request(
                4, 1,
                ("road-custom", "bridge-custom", "water-custom", "road-custom"),
                BridgeConnectivityRule("river-crossing", BridgeOrientation.HORIZONTAL, "ground", 1, 0, 2, 0),
            )
            request_path = root / "tilemap-request.json"
            dump_json(request_path, request.to_dict())
            source = root / "tileset.png"
            bridge_atlas()["page-01"].save(source)
            fingerprint = fingerprint_request(request.to_dict())
            record = ingest_image(root, source, SourceType.EXISTING_FILE, fingerprint)
            raw_image_path = root / "raw-image.json"
            dump_json(raw_image_path, record.to_dict())
            result = process_tilemap(root, request, record, root / request.output_dir)
            staging = root / result.staging_dir
            processing_result_path = staging / "processing-result.json"
            dump_json(processing_result_path, result.to_dict())
            state_path = root / "job-state.json"
            save_job(state_path, JobState(1, "job-bridge", request.asset_id, JobStatus.VERIFYING, "2026-08-02T00:00:00Z", "2026-08-02T00:00:00Z", fingerprint))
            review_path = root / "visual-review.json"
            dump_json(review_path, {"schema_version": 1, "checks": {
                "tileset-seams": "passed", "tilemap-readability": "passed", "layer-order": "passed",
                "collision-layer": "passed", "unwanted-text-or-watermark": "passed",
            }})

            with self.assertRaisesRegex(Exception, "deterministic sprite validation failed"):
                run_tilemap_validate(
                    request_path, raw_image_path, processing_result_path, root, staging,
                    root / request.output_dir / "final", review_path, state_path, "2026-08-02T00:01:00Z",
                )
            self.assertFalse((root / request.output_dir / "final").exists())
    def test_published_manifest_hashes_match_final_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request = make_tilemap_request()
            request_path = root / "tilemap-request.json"
            dump_json(request_path, request.to_dict())
            source = root / "tileset.png"
            Image.new("RGBA", (32, 32), (45, 140, 65, 255)).save(source)
            fingerprint = fingerprint_request(request.to_dict())
            record = ingest_image(root, source, SourceType.EXISTING_FILE, fingerprint)
            raw_image_path = root / "raw-image.json"
            dump_json(raw_image_path, record.to_dict())
            result = process_tilemap(root, request, record, root / request.output_dir)
            staging = root / result.staging_dir
            processing_result_path = staging / "processing-result.json"
            dump_json(processing_result_path, result.to_dict())
            state_path = root / "job-state.json"
            save_job(state_path, JobState(1, "job-forest-tiles", request.asset_id, JobStatus.VERIFYING, "2026-08-02T00:00:00Z", "2026-08-02T00:00:00Z", fingerprint))
            review_path = root / "visual-review.json"
            dump_json(review_path, {"schema_version": 1, "checks": {
                "tileset-seams": "passed",
                "tilemap-readability": "passed",
                "layer-order": "passed",
                "collision-layer": "passed",
                "unwanted-text-or-watermark": "passed",
            }})

            outcome = run_tilemap_validate(
                request_path, raw_image_path, processing_result_path, root, staging,
                root / request.output_dir, review_path, state_path, "2026-08-02T00:01:00Z",
            )

            self.assertEqual(outcome["status"], "completed")
            self.assertTrue(outcome["published"])
            manifest = load_json(root / request.output_dir / "asset-manifest.json")
            for artifact in manifest["artifacts"]:
                path = root / artifact["path"]
                self.assertTrue(path.is_file(), artifact["path"])
                self.assertEqual(sha256_file(path), artifact["sha256"])


if __name__ == "__main__":
    unittest.main()
