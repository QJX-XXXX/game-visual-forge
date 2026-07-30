from __future__ import annotations

import unittest

from tests._bootstrap import ROOT


class RepositoryContractTests(unittest.TestCase):
    def test_repository_is_skills_only_and_not_a_plugin(self) -> None:
        self.assertFalse((ROOT / ".codex-plugin").exists())
        self.assertFalse((ROOT / ".gitmodules").exists())
        self.assertTrue((ROOT / "docs" / "superpowers" / "specs").is_dir())

    def test_install_guides_are_manual_and_repo_local(self) -> None:
        for agent in ("codex", "claude"):
            guide = (ROOT / "install" / agent / "README.md").read_text(encoding="utf-8")
            self.assertIn("copy", guide.lower())
            self.assertIn("skills", guide.lower())
            self.assertIn("does not install dependencies", guide.lower())
            self.assertTrue(
                "src/" in guide or "full repository" in guide.lower(),
                f"{agent} guide must preserve src/ or require a full repository copy",
            )
            self.assertNotIn("copy each directory under `skills/`", guide.lower())
            self.assertNotIn("curl |", guide.lower())
            self.assertNotIn("invoke-webrequest", guide.lower())

    def test_package_declares_m0_version(self) -> None:
        from game_visual_forge import __version__

        self.assertEqual(__version__, "0.1.0")


if __name__ == "__main__":
    unittest.main()
