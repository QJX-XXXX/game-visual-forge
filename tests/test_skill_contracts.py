from __future__ import annotations

import subprocess
import sys
import unittest

from tests._bootstrap import ROOT


SKILLS = {
    "generate-2d-sprite": {
        "description": 'description: "Generate production-oriented 2D game assets from natural-language requests, references, or existing images, including characters, creatures, props, effects, frames, sheets, and transparent exports."',
        "required_body_fragments": (
            "Agent 原生工具",
            "原生不支持时，询问是否使用第三方；原生生成失败或质量不达标时，询问“继续尝试原生”或“使用第三方”。",
            "每次都由用户选择即梦或通义万相",
            "独立付费确认",
            "不得自动安装工具",
            "不得自动重新提交失败或 `submission_unknown` 的付费任务。",
        ),
    },
    "generate-2d-map": {
        "description": 'description: "Generate production-oriented 2D game maps with explicit visual, layer, runtime-object, collision, and export models."',
        "required_body_fragments": (
            "Agent 原生工具",
            "原生不支持时，询问是否使用第三方；原生失败或质量不达标时，询问“继续尝试原生”或“使用第三方”。",
            "每次都由用户选择即梦或通义万相",
            "独立付费确认",
            "不得自动安装工具",
            "不得自动重新提交失败或 `submission_unknown` 的任务。",
        ),
    },
    "video-to-2d-sprite": {
        "description": 'description: "Convert generated or existing video into 2D Sprite animation with safe provider selection, recoverable jobs, frame extraction, sampling, cleanup, alignment, and exports."',
        "required_body_fragments": (
            "Agent 原生工具",
            "原生不支持时询问是否使用第三方；原生失败或质量不达标时询问“继续尝试原生”或“使用第三方”。",
            "每次都由用户选择即梦或通义万相",
            "MiniMax REST、MiniMax CLI、Dreamina CLI、即梦视觉 REST、Grok/Agent 原生视频工具和已有 MP4。",
            "任何第三方任务都必须先明确选择来源，再显示模型、模式、素材和费用，并取得独立付费确认。",
            "不得自动安装工具",
            "不得自动重新提交失败或 `submission_unknown` 的任务",
        ),
    },
}


class SkillContractTests(unittest.TestCase):
    def test_each_skill_has_exact_frontmatter_description_agent_metadata_and_launcher(self) -> None:
        for name, contract in SKILLS.items():
            root = ROOT / "skills" / name
            skill = (root / "SKILL.md").read_text(encoding="utf-8")
            self.assertTrue(skill.startswith("---\n"))
            self.assertIn(f"name: {name}", skill)

            frontmatter = skill.split("---\n", 2)[1]
            frontmatter_lines = frontmatter.splitlines()
            description_lines = [line for line in frontmatter_lines if line.startswith("description: ")]
            self.assertEqual(description_lines, [contract["description"]])

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

    def test_each_skill_contains_required_routing_and_safety_rules(self) -> None:
        for name, contract in SKILLS.items():
            skill = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            for required in contract["required_body_fragments"]:
                self.assertIn(required, skill, f"{name} missing required fragment: {required}")
            self.assertNotIn("fal.ai", skill)

    def test_readme_uses_supported_launcher_and_documents_exact_routing_rules(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("python -m game_visual_forge", readme)
        self.assertIn("python skills/generate-2d-sprite/scripts/run.py dry-run", readme)

        for required in (
            "native supported -> native path",
            "native unsupported -> user chooses third party/local/existing",
            "native failure or quality rejection -> defined fallback/choice only after confirmation",
            "every Dreamina/Wanxiang third-party attempt has explicit provider/model/parameter/cost confirmation and no silent resubmission",
        ):
            self.assertIn(required, readme)


if __name__ == "__main__":
    unittest.main()
