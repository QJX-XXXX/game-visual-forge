from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tests._bootstrap import ROOT  # noqa: F401
from game_visual_forge.contracts import (
    AtlasPageDefinition,
    SourcePreference,
    SourceType,
    TileDefinition,
    TileLayer,
    TileAtlasSourceRecord,
    TileMapRequest,
    TileMapSourceSet,
    TileSemanticRole,
    TileSetProfile,
)
from game_visual_forge.processing.images import ingest_image, sha256_file
from game_visual_forge.processing.tilemap import process_tilemap
from game_visual_forge.quality.tilemap import build_tilemap_asset_manifest, validate_tilemap_outputs


def coherent_request(**changes) -> TileMapRequest:
    tiles = tuple(
        TileDefinition(f"cell-{x}-{y}", x, y, semantic_role=TileSemanticRole.TERRAIN, atlas_id="foundation")
        for y in range(2)
        for x in range(2)
    )
    request = TileMapRequest(
        1,
        "coherent-fixture",
        "coherent foundation fixture",
        "outputs/coherent-fixture/final",
        SourcePreference.EXISTING_FILE,
        48,
        48,
        2,
        2,
        2,
        2,
        tiles,
        (TileLayer("ground", 0, True, tuple(tile.tile_id for tile in tiles)),),
        "Coherent Fixture",
        "Assets/GameVisualForge/coherent-fixture",
        pixels_per_unit=48,
        atlas_pages=(AtlasPageDefinition("foundation", 2, 2, 48, 48, "foundation-only art"),),
        tileset_profile=TileSetProfile.COHERENT_FOUNDATION,
        max_tile_count=4,
        foundation_prompt_path="source/foundation.prompt.txt",
    )
    return TileMapRequest(**{**request.__dict__, **changes})


class CoherentFoundationContractTests(unittest.TestCase):
    def test_round_trip_contract(self) -> None:
        request = coherent_request()
        self.assertEqual(request.expected_atlas_size, (96, 96))
        self.assertEqual(request.to_dict()["foundation_prompt_path"], "source/foundation.prompt.txt")
        self.assertEqual(TileMapRequest.from_dict(request.to_dict()), request)

    def test_requires_prompt_and_map_sized_atlas(self) -> None:
        with self.assertRaisesRegex(ValueError, "foundation_prompt_path"):
            coherent_request(foundation_prompt_path=None)
        with self.assertRaisesRegex(ValueError, "match map dimensions"):
            coherent_request(atlas_pages=(AtlasPageDefinition("foundation", 1, 2, 48, 48, "wrong"),))

    def test_requires_one_unique_tile_per_map_cell(self) -> None:
        request = coherent_request()
        with self.assertRaisesRegex(ValueError, "one tile per map cell"):
            coherent_request(tiles=request.tiles[:-1], max_tile_count=4)
        with self.assertRaisesRegex(ValueError, "matching atlas coordinate"):
            coherent_request(layers=(TileLayer("ground", 0, True, ("cell-1-0", "cell-0-0", "cell-0-1", "cell-1-1")),))


class CoherentFoundationProcessingTests(unittest.TestCase):
    def test_processing_recomposes_foundation_pixel_identically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source").mkdir()
            (root / "source/foundation.prompt.txt").write_text("foundation-only prompt\n", encoding="utf-8")
            source = root / "foundation.png"
            image = Image.new("RGBA", (96, 96), (0, 0, 0, 255))
            for y in range(2):
                for x in range(2):
                    image.paste((30 + x * 80, 50 + y * 80, 90, 255), (x * 48, y * 48, (x + 1) * 48, (y + 1) * 48))
            image.save(source)
            request = coherent_request()
            record = ingest_image(root, source, SourceType.EXISTING_FILE, "a" * 64)

            source_set = TileMapSourceSet(1, (TileAtlasSourceRecord("foundation", record),))
            result = process_tilemap(root, request, source_set, root / request.output_dir)
            staging = root / result.staging_dir

            self.assertEqual(result.foundation_path, "foundation.png")
            self.assertEqual(result.foundation_prompt_path, "foundation.prompt.txt")
            self.assertEqual(result.foundation_recomposition_path, "foundation-recomposition.png")
            self.assertEqual(sha256_file(staging / result.foundation_path), sha256_file(staging / result.foundation_recomposition_path))
            self.assertEqual((staging / result.foundation_prompt_path).read_text(encoding="utf-8"), "foundation-only prompt\n")
            self.assertFalse(result.needs_attention)

            report = validate_tilemap_outputs(staging, request, source_set, result)
            check = next(item for item in report.deterministic_checks if item.check_id == "foundation-recomposition")
            self.assertEqual(check.status.value, "passed")
            manifest = build_tilemap_asset_manifest(staging, request, source_set, result, report)
            roles = {item.role for item in manifest.artifacts}
            self.assertTrue({"foundation", "foundation-prompt", "foundation-recomposition"}.issubset(roles))

    def test_modified_recomposition_fails_quality(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source").mkdir()
            (root / "source/foundation.prompt.txt").write_text("prompt\n", encoding="utf-8")
            source = root / "foundation.png"
            Image.new("RGBA", (96, 96), (40, 120, 60, 255)).save(source)
            request = coherent_request()
            record = ingest_image(root, source, SourceType.EXISTING_FILE, "b" * 64)
            source_set = TileMapSourceSet(1, (TileAtlasSourceRecord("foundation", record),))
            result = process_tilemap(root, request, source_set, root / request.output_dir)
            staging = root / result.staging_dir
            with Image.open(staging / result.foundation_recomposition_path) as opened:
                changed = opened.convert("RGBA")
            changed.putpixel((0, 0), (255, 0, 0, 255))
            changed.save(staging / result.foundation_recomposition_path)

            report = validate_tilemap_outputs(staging, request, source_set, result)

            check = next(item for item in report.deterministic_checks if item.check_id == "foundation-recomposition")
            self.assertEqual(check.status.value, "failed")
            self.assertEqual(report.deterministic_status.value, "failed")


if __name__ == "__main__":
    unittest.main()
