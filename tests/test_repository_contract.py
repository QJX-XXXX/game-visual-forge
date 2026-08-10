from __future__ import annotations

import subprocess
import unittest

from tests._bootstrap import ROOT


class RepositoryContractTests(unittest.TestCase):
    def test_readmes_have_reciprocal_language_links(self) -> None:
        english = (ROOT / "README.md").read_text(encoding="utf-8")
        chinese_path = ROOT / "README.zh-CN.md"

        self.assertTrue(chinese_path.is_file())
        chinese = chinese_path.read_text(encoding="utf-8")
        self.assertIn("[简体中文](README.zh-CN.md)", english)
        self.assertIn("[English](README.md)", chinese)
        self.assertNotIn("\n## 中文\n", english)
        self.assertNotIn("\n## English\n", chinese)

    def test_readme_background_comparison_asset_exists(self) -> None:
        relative_path = (
            "assets/readme/rembg-production-comparison-on-gray.jpg"
        )
        self.assertTrue((ROOT / relative_path).is_file())
        for readme in ("README.md", "README.zh-CN.md"):
            content = (ROOT / readme).read_text(encoding="utf-8")
            self.assertIn(f"]({relative_path})", content)

    def test_repository_is_skills_only_and_not_a_plugin(self) -> None:
        self.assertFalse((ROOT / ".codex-plugin").exists())
        self.assertFalse((ROOT / ".gitmodules").exists())
        ignore_rules = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("docs/", ignore_rules)
        self.assertIn(".superpowers/", ignore_rules)

        for internal_path in (".superpowers", "docs/superpowers"):
            result = subprocess.run(
                ["git", "ls-files", internal_path],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "", internal_path)

    def test_readmes_expose_public_skill_and_install_entrypoints(self) -> None:
        for readme_name in ("README.md", "README.zh-CN.md"):
            text = (ROOT / readme_name).read_text(encoding="utf-8")
            for required in (
                "forge-2d-map",
                "forge-2d-sprite",
                "forge-video-to-sprite",
                "install/codex/README.md",
                "install/claude/README.md",
            ):
                self.assertIn(required, text, f"{readme_name} missing public entrypoint: {required}")

    def test_readmes_stay_concise_and_do_not_duplicate_workflow(self) -> None:
        forbidden_fragments = (
            "map plan -> map route -> map ingest -> map process -> map validate",
            "### M0",
            "### M1",
            "### M2",
            "`map-quality-report.json`",
            "`Reports/unity-import-report.json`",
        )
        for readme_name in ("README.md", "README.zh-CN.md"):
            text = (ROOT / readme_name).read_text(encoding="utf-8")
            self.assertLessEqual(len(text.splitlines()), 180, readme_name)
            for forbidden in forbidden_fragments:
                self.assertNotIn(forbidden, text, f"{readme_name} duplicates internal workflow: {forbidden}")

    def test_readmes_explain_hd_cleanup_tools_and_installation(self) -> None:
        required = (
            "birefnet-general",
            'python -m pip install -e ".[image]"',
            'python -m pip install -e ".[background]"',
            'python -m pip install "rembg[cpu]"',
            'python -m pip install "rembg[gpu]"',
            'python -m pip install -e ".[matting]"',
            "U2NET_HOME",
            "PyMatting",
            "CUDA",
            "CPU",
        )
        for readme_name in ("README.md", "README.zh-CN.md"):
            text = (ROOT / readme_name).read_text(encoding="utf-8")
            for fragment in required:
                self.assertIn(fragment, text, f"{readme_name} missing HD cleanup guidance: {fragment}")

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

    def test_video_processing_docs_and_dependencies_are_explicit(self) -> None:
        for readme_name in ("README.md", "README.zh-CN.md"):
            text = (ROOT / readme_name).read_text(encoding="utf-8")
            for fragment in ("FFmpeg", "FFprobe", "mmx", "dreamina", "MINIMAX_API_KEY", "JIMENG_ACCESS_KEY"):
                self.assertIn(fragment, text, f"{readme_name} missing video setup guidance: {fragment}")
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        base = pyproject.split("[project.optional-dependencies]", 1)[0]
        self.assertNotIn("ffmpeg", base.lower())
        self.assertNotIn("minimax", base.lower())
        self.assertNotIn("jimeng", base.lower())

    def test_package_declares_m0_version(self) -> None:
        from game_visual_forge import __version__

        self.assertEqual(__version__, "0.1.0")


if __name__ == "__main__":
    unittest.main()
