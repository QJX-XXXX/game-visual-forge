from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from tests._bootstrap import ROOT  # noqa: F401
from game_visual_forge.contracts import SourceType
from game_visual_forge.errors import ErrorCode, ForgeError
from game_visual_forge.processing.images import ingest_image, verify_image_unchanged


class ImageIngestTests(unittest.TestCase):
    def make_fixture(self) -> tuple[Path, Path]:
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        path = directory / "inputs" / "hero.png"
        path.parent.mkdir()
        Image.new("RGBA", (8, 4), (255, 0, 255, 255)).save(path)
        return directory, path

    def test_ingest_records_relative_path_dimensions_format_and_hash(self) -> None:
        root, path = self.make_fixture()
        record = ingest_image(root, path, SourceType.EXISTING_FILE, "a" * 64)
        self.assertEqual(record.path, "inputs/hero.png")
        self.assertEqual((record.width, record.height), (8, 4))
        self.assertEqual(record.media_format, "PNG")
        self.assertRegex(record.sha256, r"^[0-9a-f]{64}$")

    def test_changed_source_is_rejected(self) -> None:
        root, path = self.make_fixture()
        record = ingest_image(root, path, SourceType.EXISTING_FILE, "a" * 64)
        path.write_bytes(b"changed")
        with self.assertRaisesRegex(ForgeError, "changed"):
            verify_image_unchanged(root, record)

    def test_outside_repository_is_rejected(self) -> None:
        root, path = self.make_fixture()
        with self.assertRaisesRegex(ForgeError, "inside the repository"):
            ingest_image(root, Path(tempfile.gettempdir()) / "outside.png", SourceType.EXISTING_FILE, "a" * 64)

    def test_missing_pillow_has_actionable_error(self) -> None:
        with patch("game_visual_forge.processing.images._load_pillow", side_effect=ImportError):
            with self.assertRaises(ForgeError) as caught:
                ingest_image(Path("."), Path("image.png"), SourceType.EXISTING_FILE, "a" * 64)
        self.assertEqual(caught.exception.code, ErrorCode.DEPENDENCY_MISSING)
        self.assertIn("Pillow", caught.exception.message)


if __name__ == "__main__":
    unittest.main()
