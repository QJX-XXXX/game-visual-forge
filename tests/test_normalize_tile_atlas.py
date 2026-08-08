from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tests._bootstrap import ROOT  # noqa: F401
from tests.test_coherent_foundation_tilemap import coherent_request
from tests.test_tilemap_contract import make_adaptive_tilemap_request
from game_visual_forge.contracts import AtlasPageDefinition, MapSourceDecision, MapSourceType, TileFilterMode, TileMapRequest
from game_visual_forge.jobs import fingerprint_request
from game_visual_forge.processing.tilemap_atlas_normalization import (
    normalize_tilemap_atlases,
    validate_atlas_normalization_report,
)


def native_decision(request: TileMapRequest) -> MapSourceDecision:
    return MapSourceDecision(
        1,
        MapSourceType.AGENT_NATIVE,
        False,
        False,
        "native",
        fingerprint_request(request.to_dict()),
    )


def make_request(*, profile: str = "adaptive_hd", tile_width: int = 32, tile_height: int = 32, margin: int = 0, spacing: int = 0) -> TileMapRequest:
    if profile == "coherent_foundation":
        return coherent_request()
    base = make_adaptive_tilemap_request(48)
    pages = tuple(
        AtlasPageDefinition(f"page-{index:02d}", 4, 4, tile_width, tile_height, f"Page {index} forest terrain")
        for index in range(1, 4)
    )
    return TileMapRequest(**{
        **base.__dict__,
        "tile_width": tile_width,
        "tile_height": tile_height,
        "pixels_per_unit": tile_width,
        "tile_size_mode": None,
        "atlas_margin": margin,
        "atlas_spacing": spacing,
        "atlas_pages": pages,
    })


class NormalizeTileAtlasTests(unittest.TestCase):
    def test_resizes_each_page_without_reordering(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            request = make_request()
            source = root / "page-01-generated.png"
            image = Image.new("RGBA", (1024, 1024))
            colors = []
            for row in range(4):
                for column in range(4):
                    color = (column * 50, row * 50, 100 + row * 4 + column, 255)
                    colors.append(color)
                    image.paste(color, (column * 256, row * 256, (column + 1) * 256, (row + 1) * 256))
            image.save(source)

            report = normalize_tilemap_atlases(root, request, native_decision(request), (("page-01", source), ("page-02", source), ("page-03", source)), root / "normalized")

            self.assertEqual(report.status.value, "normalized")
            self.assertEqual((report.pages[0].output_width, report.pages[0].output_height), (128, 128))
            with Image.open(root / "normalized" / "page-01.png") as normalized:
                self.assertEqual(normalized.size, (128, 128))
                for index, color in enumerate(colors):
                    x = (index % 4) * 32 + 16
                    y = (index // 4) * 32 + 16
                    self.assertEqual(normalized.getpixel((x, y)), color)

    def test_non_divisible_source_and_margin_spacing_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            request = make_request(margin=2, spacing=1)
            source = root / "source.png"
            Image.new("RGBA", (1254, 1254), (24, 80, 120, 255)).save(source)
            report = normalize_tilemap_atlases(root, request, native_decision(request), (("page-01", source), ("page-02", source), ("page-03", source)), root / "normalized")
            self.assertEqual((report.pages[0].output_width, report.pages[0].output_height), (135, 135))
            with Image.open(root / "normalized" / "page-01.png") as normalized:
                self.assertEqual(normalized.size, (135, 135))
                self.assertEqual(normalized.getpixel((0, 0)), (0, 0, 0, 0))
                self.assertEqual(normalized.getpixel((2, 2)), (24, 80, 120, 255))

    def test_exact_size_is_not_required_and_report_validates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            request = make_request()
            source = root / "exact.png"
            Image.new("RGBA", request.expected_atlas_sizes["page-01"], (20, 30, 40, 255)).save(source)
            pages = (("page-01", source), ("page-02", source), ("page-03", source))
            report = normalize_tilemap_atlases(root, request, native_decision(request), pages, root / "normalized")
            self.assertEqual(report.status.value, "not_required")
            validate_atlas_normalization_report(root, request, native_decision(request), report, pages)

    def test_rejects_incompatible_grid_and_coherent_foundation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            request = make_request()
            source = root / "wide-grid.png"
            Image.new("RGBA", (1024, 768), (20, 30, 40, 255)).save(source)
            with self.assertRaisesRegex(ValueError, "aspect ratio"):
                normalize_tilemap_atlases(root, request, native_decision(request), (("page-01", source), ("page-02", source), ("page-03", source)), root / "normalized")

            foundation = make_request(profile="coherent_foundation")
            with self.assertRaisesRegex(ValueError, "coherent_foundation"):
                normalize_tilemap_atlases(root, foundation, native_decision(foundation), (("page-01", source),), root / "foundation-normalized")

    def test_bilinear_uses_lanczos_and_non_native_requires_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            request = TileMapRequest(**{**make_request().__dict__, "filter_mode": TileFilterMode.BILINEAR})
            source = root / "source.png"
            Image.new("RGBA", (1024, 1024), (20, 30, 40, 255)).save(source)
            external = MapSourceDecision(1, MapSourceType.EXISTING_FILE, False, False, "existing", fingerprint_request(request.to_dict()))
            with self.assertRaisesRegex(ValueError, "agent-native"):
                normalize_tilemap_atlases(root, request, external, (("page-01", source), ("page-02", source), ("page-03", source)), root / "normalized")
            report = normalize_tilemap_atlases(root, request, external, (("page-01", source), ("page-02", source), ("page-03", source)), root / "normalized", allow_non_native=True)
            self.assertEqual(report.pages[0].resampling, "lanczos")

    def test_normalization_never_overwrites_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            request = make_request()
            source = root / "page-01.png"
            Image.new("RGBA", (1024, 1024), (20, 30, 40, 255)).save(source)
            with self.assertRaisesRegex(ValueError, "must not overwrite"):
                normalize_tilemap_atlases(
                    root,
                    request,
                    native_decision(request),
                    (("page-01", source), ("page-02", source), ("page-03", source)),
                    root,
                )


if __name__ == "__main__":
    unittest.main()
