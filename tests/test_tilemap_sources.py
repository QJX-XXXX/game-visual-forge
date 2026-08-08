from __future__ import annotations

import unittest
from pathlib import Path

from tests._bootstrap import ROOT  # noqa: F401
from tests.test_tilemap_contract import make_adaptive_tilemap_request, make_tilemap_request
from game_visual_forge.contracts import (
    RawImageRecord,
    SourceType,
    TileAtlasSourceRecord,
    TileMapSourceSet,
    load_tilemap_source_set,
    parse_atlas_page_argument,
)


def image_record(fingerprint: str = "a" * 64) -> RawImageRecord:
    return RawImageRecord(1, "assets/tileset.png", "b" * 64, 64, 64, "PNG", SourceType.EXISTING_FILE, fingerprint)


class TilemapSourceTests(unittest.TestCase):
    def test_legacy_raw_image_is_wrapped_as_page_one(self) -> None:
        request = make_tilemap_request()
        source_set = load_tilemap_source_set(image_record().to_dict(), request)
        self.assertEqual(source_set.pages[0].atlas_id, "page-01")
        self.assertEqual(source_set.pages[0].image, image_record())

    def test_multi_page_source_ids_must_match_request(self) -> None:
        request = make_adaptive_tilemap_request(32)
        payload = TileMapSourceSet(1, (TileAtlasSourceRecord("wrong", image_record()),)).to_dict()
        with self.assertRaisesRegex(ValueError, "atlas page sources"):
            load_tilemap_source_set(payload, request)

    def test_multi_page_source_round_trip(self) -> None:
        request = make_adaptive_tilemap_request(32)
        source_set = TileMapSourceSet(
            1,
            (
                TileAtlasSourceRecord("page-01", image_record()),
                TileAtlasSourceRecord("page-02", image_record()),
            ),
        )
        self.assertEqual(load_tilemap_source_set(source_set.to_dict(), request), source_set)

    def test_atlas_page_argument_requires_id_and_path(self) -> None:
        self.assertEqual(parse_atlas_page_argument("page-02=tiles/page-02.png"), ("page-02", Path("tiles/page-02.png")))
        with self.assertRaisesRegex(ValueError, "atlas-id=path"):
            parse_atlas_page_argument("page-02")


if __name__ == "__main__":
    unittest.main()
