from __future__ import annotations

import subprocess
import sys
import unittest

from tests._bootstrap import ROOT


SKILLS = {
    "generate-2d-sprite": "Generate production-oriented 2D game assets",
    "generate-2d-map": "Generate production-oriented 2D game maps",
    "video-to-2d-sprite": "Convert generated or existing video into 2D Sprite animation",
}


class SkillContractTests(unittest.TestCase):
    def test_each_skill_has_frontmatter_agent_metadata_and_launcher(self) -> None:
        for name, description in SKILLS.items():
            root = ROOT / "skills" / name
            skill = (root / "SKILL.md").read_text(encoding="utf-8")
            self.assertTrue(skill.startswith("---\n"))
            self.assertIn(f"name: {name}", skill)
            self.assertIn(f'description: "{description}', skill)
            self.assertTrue((root / "agents" / "openai.yaml").is_file())
            self.assertTrue((root / "scripts" / "run.py").is_file())

    def test_skill_launchers_expose_common_cli_help(self) -> None:
        for name in SKILLS:
            launcher = ROOT / "skills" / name / "scripts" / "run.py"
            result = subprocess.run(
                [sys.executable, str(launcher), "--help"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("dry-run", result.stdout)

    def test_skills_forbid_silent_provider_selection_and_paid_submission(self) -> None:
        combined = "\n".join(
            (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            for name in SKILLS
        )
        for required in (
            "Agent 原生",
            "即梦",
            "通义万相",
            "每次都由用户选择",
            "付费确认",
            "不得自动安装",
            "不得自动重新提交",
        ):
            self.assertIn(required, combined)
        self.assertNotIn("fal.ai", combined)


if __name__ == "__main__":
    unittest.main()
