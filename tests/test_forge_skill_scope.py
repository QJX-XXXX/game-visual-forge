from __future__ import annotations

import unittest
from pathlib import Path

from tests._bootstrap import ROOT  # noqa: F401


class ForgeSkillScopeTests(unittest.TestCase):
    def test_repository_owns_exactly_three_forge_skills(self) -> None:
        actual = {path.name for path in (ROOT / "skills").iterdir() if path.is_dir()}
        self.assertEqual(actual, {"forge-2d-map", "forge-2d-sprite", "forge-video-to-sprite"})

    def test_map_skill_documents_enforced_workflow(self) -> None:
        text = (ROOT / "skills" / "forge-2d-map" / "SKILL.md").read_text(encoding="utf-8")
        for phrase in ("needs_user_input", "needs_user_confirmation", "preassembly-review", "assembled-review-sheet.png", "scene_acceptance_status=not_run", "exactly two user approval gates"):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
