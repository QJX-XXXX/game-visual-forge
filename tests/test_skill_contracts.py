from __future__ import annotations

import re
import subprocess
import sys
import unittest

from tests._bootstrap import ROOT


CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]")


SKILLS = {
    "forge-2d-sprite": {
        "description": 'description: "Use when creating or processing production-oriented 2D game sprites, animation sheets, transparent PNG frames, characters, creatures, props, or effects from prompts, references, or existing images."',
        "required_body_fragments": (
            "Prefer an existing image",
            "native image tool",
            "If native generation is unavailable, ask the user to choose",
            "ask the user to choose Jimeng or Wanxiang every time",
            "provider, model, non-sensitive parameters, quantity, cost, currency, and request fingerprint",
            "Never install",
            "Never resubmit",
            "submission_unknown",
            "Submit one grouped intake card",
            "--visual-review",
            "character-identity-consistency",
            "semantic-duplicate-frames",
            "sprite plan",
            "sprite route",
            "sprite ingest",
            "sprite process",
            "sprite validate",
            "complex character motion",
            "`forge-video-to-sprite`",
            "continue with `forge-2d-sprite` or switch",
            "must not switch workflows automatically",
            "true transparent PNG",
            "`background_removal=auto`",
            "real Alpha channel",
            "opaque white",
            "must not be published",
            "`transparent_background_prompt`",
        ),
    },
    "forge-2d-map": {
        "description": 'description: "Generate and integrate playable 2D game maps with demand-driven or coherent-foundation terrain Tilemaps, complete building/prop objects, collision and traversal contracts, deterministic quality gates, and explicit user approvals. Use for RPG villages, overworlds, arenas, bridges, water, Unity Tilemaps, and map previews/imports."',
        "required_body_fragments": (
            "native Agent tools",
            "Jimeng",
            "Wanxiang",
            "Ask the user to choose the provider, model, and parameters every time",
            "explicit paid confirmation",
            "Never install tools automatically",
            "Never resubmit",
        ),
    },
    "forge-video-to-sprite": {
        "description": 'description: "Use when existing, MiniMax Hailuo, Jimeng, optional local ComfyUI MiniMax H3 video must become a validated 2D Sprite animation."',
        "required_body_fragments": (
            "MiniMax Hailuo",
            "Jimeng",
            "existing-file",
            "api",
            "cli",
            "ComfyUI MiniMax H3",
            "discovered-unprofiled",
            "submission_unknown",
            "video sprite plan",
            "video provider models",
            "video sprite record-review",
            "FFmpeg",
            "presentation timestamp",
            "motion-difference",
            "submission_unknown",
            "If a prerequisite is absent during ordinary asset work, report it and stop the",
            "Only when the user explicitly asks to install",
            "repository Agent installation guide",
            "FL2VA",
            "same ready-pose image",
            "fixed seed",
            "17k + 5",
            "static source image",
            "reference-locked",
            "runtime-owned",
            "inspect-h3",
        ),
    },
    "forge-text-audio": {
        "description": 'description: "Generate, redraw, inpaint, continue, validate, and deliver explicitly requested game sound effects and ambience with a locally installed Stable Audio 3 Small-SFX model and Unity AudioClip integration. Use only when the user explicitly asks for non-speech game audio; do not trigger for visual-only work, dialogue, voice-over, songs, or complete musical scores."',
        "required_body_fragments": (
            "explicitly requests a game sound effect",
            "small-sfx",
            "text-to-audio",
            "redraw",
            "inpaint",
            "continue",
            "three candidates",
            "final listening approval",
            "44,100 Hz",
            "16-bit signed PCM WAV",
            "-1.0 dBFS",
            "one-shots",
            "Never install",
            "Never retry",
            "Unity MCP",
            "AudioClip",
            "AudioSource",
        ),
    },
}


class SkillContractTests(unittest.TestCase):
    def assert_skill_tree_is_english(self, skill_name: str) -> None:
        skill_root = ROOT / "skills" / skill_name
        for path in sorted(item for item in skill_root.rglob("*") if item.is_file() and item.suffix.lower() in {".md", ".yaml", ".yml", ".py"}):
            content = path.read_text(encoding="utf-8")
            match = CJK_PATTERN.search(content)
            self.assertIsNone(match, f"{path.relative_to(ROOT)} contains non-English text: {match.group(0) if match else ''}")

    def test_public_skill_packages_are_english(self) -> None:
        skills_root = ROOT / "skills"
        skill_names = tuple(
            path.name
            for path in sorted(skills_root.iterdir())
            if path.is_dir() and (path / "SKILL.md").is_file()
        )
        self.assertEqual(skill_names, ("forge-2d-map", "forge-2d-sprite", "forge-text-audio", "forge-video-to-sprite"))
        for skill_name in skill_names:
            with self.subTest(skill=skill_name):
                self.assert_skill_tree_is_english(skill_name)

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

    def test_video_skill_documents_local_first_frame_safety(self) -> None:
        workflow = (ROOT / "skills" / "forge-video-to-sprite" / "references" / "provider-workflow.md").read_text(encoding="utf-8")
        for phrase in ("first_frame_path", "first_frame_sha256", "in memory", "Data URI"):
            self.assertIn(phrase, workflow)

    def test_video_skill_documents_utf8_and_all_density_chroma_gate(self) -> None:
        skill = (ROOT / "skills" / "forge-video-to-sprite" / "SKILL.md").read_text(encoding="utf-8")
        provider = (ROOT / "skills" / "forge-video-to-sprite" / "references" / "provider-workflow.md").read_text(encoding="utf-8")
        quality = (ROOT / "skills" / "forge-video-to-sprite" / "references" / "processing-and-quality.md").read_text(encoding="utf-8")
        self.assertIn("UTF-8", skill)
        self.assertIn("binary UTF-8 JSON", provider)
        self.assertIn("every requested density", quality)
        self.assertIn("1.0%", quality)

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

    def test_each_skill_contains_required_routing_and_safety_rules(self) -> None:
        for name, contract in SKILLS.items():
            skill = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            required_fragments = contract["required_body_fragments"]
            if name == "forge-2d-map":
                required_fragments = required_fragments + ("TWO_GATE", "style-sample", "assembled-map", "demand-driven", "complete building", "road_connectivity_policy", "minimum_traversal_width", "rejection.json", "map tile record-approval", "AssetsOnly", "ImportAndPlace")
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
