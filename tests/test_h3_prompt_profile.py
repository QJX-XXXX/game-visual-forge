from __future__ import annotations

import unittest
from pathlib import Path

from tests._bootstrap import ROOT


SKILL = ROOT / "skills/forge-video-to-sprite/SKILL.md"
PROFILE = ROOT / "skills/forge-video-to-sprite/references/h3-character-quality-profile.md"


class H3PromptProfileTests(unittest.TestCase):
    def test_local_h3_skill_routes_character_jobs_to_profile(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        self.assertIn("references/h3-character-quality-profile.md", skill)
        self.assertTrue(PROFILE.is_file())

    def test_profile_contains_quality_and_provenance_contract(self) -> None:
        profile = PROFILE.read_text(encoding="utf-8")
        required_fragments = (
            "integrated_multimodal_description",
            "motion blur",
            "temporal ghosting",
            "fixed H3 seed",
            "I2VA",
            "FL2VA",
            "prompt_id",
            "visual review",
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, profile)

    def test_profile_does_not_create_a_universal_weapon_contradiction(self) -> None:
        profile = PROFILE.read_text(encoding="utf-8")
        self.assertNotIn("No weapons", profile.replace("`No weapons`", ""))
        self.assertNotIn("[placeholder]", profile.lower())


if __name__ == "__main__":
    unittest.main()
