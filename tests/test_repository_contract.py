from __future__ import annotations

import unittest

from tests._bootstrap import ROOT


class RepositoryContractTests(unittest.TestCase):
    def test_repository_is_skills_only_and_not_a_plugin(self) -> None:
        self.assertFalse((ROOT / ".codex-plugin").exists())
        self.assertFalse((ROOT / ".gitmodules").exists())
        self.assertTrue((ROOT / "docs" / "superpowers" / "specs").is_dir())

    def test_package_declares_m0_version(self) -> None:
        from game_visual_forge import __version__

        self.assertEqual(__version__, "0.1.0")


if __name__ == "__main__":
    unittest.main()
