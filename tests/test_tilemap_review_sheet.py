from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tests._bootstrap import ROOT  # noqa: F401
from game_visual_forge.contracts.approval import ASSEMBLED_APPROVAL_ROLES
from game_visual_forge.processing.tilemap_review_sheet import render_assembled_review_sheet
from tests.tilemap_workflow_fixtures import build_workflow_request_payload
from game_visual_forge.contracts import TileMapRequest


class TilemapReviewSheetTests(unittest.TestCase):
    def test_assembled_approval_roles_include_review_sheet_first(self) -> None:
        self.assertEqual(ASSEMBLED_APPROVAL_ROLES, ("review-sheet", "tilemap-preview", "gameplay-crop", "tilemap-placement", "tilemap-objects", "tilemap-collision", "asset-set"))

    def test_render_sheet_is_larger_than_preview_panel(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            staging = Path(directory)
            request = TileMapRequest.from_dict(build_workflow_request_payload())
            preview = Image.new("RGBA", (request.map_width * request.tile_width, request.map_height * request.tile_height), (30, 120, 50, 255))
            preview.save(staging / "tilemap-preview.png")
            Image.new("RGBA", (request.tile_width, request.tile_height), (220, 30, 30, 180)).save(staging / "tilemap-collision-preview.png")
            result = render_assembled_review_sheet(staging, request, {"tilemap-preview": "tilemap-preview.png", "tilemap-collision": "tilemap-collision-preview.png"})
            with Image.open(staging / result) as sheet:
                self.assertGreater(sheet.width, preview.width)
                self.assertGreater(sheet.height, preview.height)


if __name__ == "__main__":
    unittest.main()
