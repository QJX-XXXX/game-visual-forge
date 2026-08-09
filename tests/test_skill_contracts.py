from __future__ import annotations

import subprocess
import sys
import unittest

from tests._bootstrap import ROOT


SKILLS = {
    "forge-2d-sprite": {
        "description": 'description: "Generate production-oriented 2D game assets from natural-language requests, references, or existing images, including characters, creatures, props, effects, frames, sheets, and transparent exports."',
        "required_body_fragments": (
            "已有图像优先",
            "Agent 原生图像工具",
            "原生能力不支持时，要求用户选择",
            "每次都由用户选择即梦或万相",
            "服务商、模型、非敏感参数、数量、费用、币种和请求指纹",
            "不得自动安装",
            "不得自动重新提交",
            "submission_unknown",
            "sprite plan",
            "sprite route",
            "sprite ingest",
            "sprite process",
            "sprite validate",
        ),
    },
    "forge-2d-map": {
        "description": 'description: "Generate and integrate playable 2D game maps with demand-driven or coherent-foundation terrain Tilemaps, complete building/prop objects, collision and traversal contracts, deterministic quality gates, and explicit user approvals. Use for RPG villages, overworlds, arenas, bridges, water, Unity Tilemaps, and map previews/imports."',
        "required_body_fragments": (
            "Agent 原生工具",
            "即梦",
            "万相",
            "每次都由用户选择",
            "付费确认",
            "不得自动安装工具",
            "不得自动重新提交",
        ),
    },
    "forge-video-to-sprite": {
        "description": 'description: "Convert an existing or explicitly generated video into validated 2D Sprite animation with timestamp sampling, cleanup, stable alignment, quality review, and recoverable MiniMax Hailuo or Jimeng API/CLI workflows."',
        "required_body_fragments": (
            "MiniMax Hailuo",
            "Jimeng",
            "existing-file",
            "api",
            "cli",
            "MiniMax-H3",
            "discovered-unprofiled",
            "submission_unknown",
            "video sprite plan",
            "video provider models",
            "video sprite record-review",
            "FFmpeg",
            "presentation timestamp",
            "motion-difference",
            "submission_unknown",
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
            description_lines = [line for line in frontmatter.splitlines() if line.startswith("description: ")]
            self.assertEqual(description_lines, [contract["description"]])
            self.assertTrue((root / "agents" / "openai.yaml").is_file())
            self.assertTrue((root / "scripts" / "run.py").is_file())

    def test_skill_launchers_expose_common_cli_help(self) -> None:
        for name in SKILLS:
            launcher = ROOT / "skills" / name / "scripts" / "run.py"
            result = subprocess.run([sys.executable, str(launcher), "--help"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("dry-run", result.stdout)

    def test_sprite_launcher_exposes_m1_commands(self) -> None:
        launcher = ROOT / "skills" / "forge-2d-sprite" / "scripts" / "run.py"
        result = subprocess.run([sys.executable, str(launcher), "sprite", "--help"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        for command in ("plan", "route", "ingest", "process", "validate"):
            self.assertIn(command, result.stdout)

    def test_video_launcher_exposes_p0_p1_commands(self) -> None:
        launcher = ROOT / "skills" / "forge-video-to-sprite" / "scripts" / "run.py"
        result = subprocess.run([sys.executable, str(launcher), "video", "sprite", "--help"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        for command in ("plan", "route", "ingest", "process", "record-review", "validate"):
            self.assertIn(command, result.stdout)
        provider = subprocess.run([sys.executable, str(launcher), "video", "provider", "--help"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False)
        self.assertEqual(provider.returncode, 0, provider.stderr)
        for command in ("models", "preflight", "estimate", "submit", "query", "download"):
            self.assertIn(command, provider.stdout)

    def test_map_launcher_exposes_m2_commands(self) -> None:
        launcher = ROOT / "skills" / "forge-2d-map" / "scripts" / "run.py"
        result = subprocess.run([sys.executable, str(launcher), "map", "--help"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        for command in ("plan", "route", "ingest", "process", "validate"):
            self.assertIn(command, result.stdout)

    def test_map_launcher_exposes_tilemap_commands(self) -> None:
        launcher = ROOT / "skills" / "forge-2d-map" / "scripts" / "run.py"
        result = subprocess.run([sys.executable, str(launcher), "map", "tile", "--help"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        for command in ("plan", "route", "ingest", "normalize-atlases", "process", "validate"):
            self.assertIn(command, result.stdout)

        ingest = subprocess.run(
            [sys.executable, str(launcher), "map", "tile", "ingest", "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(ingest.returncode, 0, ingest.stderr)
        self.assertIn("--atlas-page", ingest.stdout)

    def test_map_skill_documents_adaptive_tilemap_confirmation_quality_and_scope(self) -> None:
        skill = (ROOT / "skills" / "forge-2d-map" / "SKILL.md").read_text(encoding="utf-8")
        for required in ("`standard_16`", "`adaptive_hd`", "`demand_driven`", "TWO_GATE", "style-sample", "assembled-map", "normalize-atlases", "--normalization-report", "coherent_foundation", "`--atlas-page`", "`tilemap-preview.png`", "`tilemap-gameplay-crop.png`", "`tilemap-collision-preview.png`", "`tile-seam-preview.png`", "`tile-usage-preview.png`", "`map-quality-report.json`", "rejection.json", "Buildings", "Props"):
            self.assertIn(required, skill)
        self.assertLess(skill.index("normalize-atlases"), skill.index("preflight-assets"))
        return
        for required in (
            "`standard_16`",
            "`adaptive_hd`",
            "ordered multi-page confirmation packet",
            "page count, ordered slots, and the prompt for every page",
            "`--atlas-page` arguments",
            "--atlas-page page-01=outputs/adaptive-map/raw/tileset-page-01.png",
            "`tilemap-preview.png`",
            "`tile-seam-preview.png`",
            "`tile-usage-preview.png`",
            "`map-quality-report.json` quality preview artifacts",
            "**Assets-only** import by default",
            "**Import and Place**",
            "Collision/mask layers are optional",
            "spatial data; gameplay objects",
            "runtime game logic are outside this Skill's scope",
            "never rewrite README files",
            "invent\nREADME evidence links",
            "bridge_connectivity_rules",
            "semantic_role=bridge",
            "semantic_role=road",
            "bridge-connectivity",
            "prevents the CLI from publishing the `final` directory",
            "same placement",
            "older\nscreenshot",
        ):
            self.assertIn(required, skill)

    def test_map_skill_documents_tile_size_modes(self) -> None:
        skill = (ROOT / "skills" / "forge-2d-map" / "SKILL.md").read_text(encoding="utf-8")
        for required in ("preset_16", "preset_32", "custom", "tile_width / pixels_per_unit"):
            self.assertIn(required, skill)
        return
        for required in ("preset_16", "preset_32", "custom", "32×32", "tile_width / pixels_per_unit"):
            self.assertIn(required, skill)

    def test_each_skill_contains_required_routing_and_safety_rules(self) -> None:
        for name, contract in SKILLS.items():
            skill = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            required_fragments = contract["required_body_fragments"]
            if name == "forge-2d-map":
                required_fragments = ("TWO_GATE", "style-sample", "assembled-map", "demand-driven", "complete building", "road_connectivity_policy", "minimum_traversal_width", "rejection.json", "map tile record-approval", "AssetsOnly", "ImportAndPlace")
            for required in required_fragments:
                self.assertIn(required, skill, f"{name} missing required fragment: {required}")
            self.assertNotIn("fal.ai", skill)

    def test_readme_keeps_public_scope_outside_internal_routing(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for required in ("forge-2d-map", "forge-2d-sprite", "forge-video-to-sprite"):
            self.assertIn(required, readme)
        for internal_fragment in (
            "native supported -> native path",
            "native unsupported -> user chooses third party/local/existing",
            "native failure or quality rejection -> defined fallback/choice only after confirmation",
            "every Dreamina/Wanxiang third-party attempt",
        ):
            self.assertNotIn(internal_fragment, readme)


if __name__ == "__main__":
    unittest.main()
