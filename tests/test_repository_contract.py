from __future__ import annotations

import subprocess
import unittest

from tests._bootstrap import ROOT


class RepositoryContractTests(unittest.TestCase):
    def test_readmes_have_reciprocal_language_links(self) -> None:
        english = (ROOT / "README.md").read_text(encoding="utf-8")
        chinese = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
        self.assertIn("[简体中文](README.zh-CN.md)", english)
        self.assertIn("[English](README.md)", chinese)
        self.assertNotIn("\n## 中文\n", english)
        self.assertNotIn("\n## English\n", chinese)

    def test_readme_background_comparison_asset_exists(self) -> None:
        relative_path = "assets/readme/rembg-production-comparison-on-gray.jpg"
        self.assertTrue((ROOT / relative_path).is_file())
        for readme in ("README.md", "README.zh-CN.md"):
            self.assertIn(f"]({relative_path})", (ROOT / readme).read_text(encoding="utf-8"))

    def test_repository_is_skills_only_and_not_a_plugin(self) -> None:
        self.assertFalse((ROOT / ".codex-plugin").exists())
        self.assertFalse((ROOT / ".gitmodules").exists())
        ignore_rules = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("docs/", ignore_rules)
        self.assertIn(".superpowers/", ignore_rules)
        allowed_internal = {
            "docs/superpowers/specs/2026-08-14-stable-audio-3-runtime-migration-design.md",
            "docs/superpowers/plans/2026-08-14-stable-audio-3-runtime-migration.md",
            "docs/superpowers/specs/2026-08-14-audio-one-shot-peak-normalization-design.md",
            "docs/superpowers/plans/2026-08-14-audio-one-shot-peak-normalization.md",
        }
        for internal_path in (".superpowers", "docs/superpowers"):
            result = subprocess.run(["git", "ls-files", internal_path], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            tracked = {line for line in result.stdout.splitlines() if line}
            if internal_path == ".superpowers":
                self.assertEqual(tracked, set(), internal_path)
            else:
                self.assertTrue(tracked.issubset(allowed_internal), tracked)

    def test_readmes_expose_public_skill_and_install_entrypoints(self) -> None:
        for readme_name in ("README.md", "README.zh-CN.md"):
            text = (ROOT / readme_name).read_text(encoding="utf-8")
            for required in ("forge-2d-map", "forge-2d-sprite", "forge-video-to-sprite", "forge-text-audio", "install/codex/README.md", "install/claude/README.md"):
                self.assertIn(required, text, f"{readme_name} missing public entrypoint: {required}")

    def test_readmes_stay_concise_and_do_not_duplicate_workflow(self) -> None:
        forbidden_fragments = ("map plan -> map route -> map ingest -> map process -> map validate", "### M0", "### M1", "### M2", "`map-quality-report.json`", "`Reports/unity-import-report.json`")
        for readme_name in ("README.md", "README.zh-CN.md"):
            text = (ROOT / readme_name).read_text(encoding="utf-8")
            self.assertLessEqual(len(text.splitlines()), 180, readme_name)
            for forbidden in forbidden_fragments:
                self.assertNotIn(forbidden, text, f"{readme_name} duplicates internal workflow: {forbidden}")

    def test_readmes_explain_hd_cleanup_tools_and_installation(self) -> None:
        required = ("birefnet-general", 'python -m pip install -e ".[image]"', 'python -m pip install -e ".[background]"', 'python -m pip install "rembg[cpu]"', 'python -m pip install "rembg[gpu]"', 'python -m pip install -e ".[matting]"', "U2NET_HOME", "PyMatting", "CUDA", "CPU")
        for readme_name in ("README.md", "README.zh-CN.md"):
            text = (ROOT / readme_name).read_text(encoding="utf-8")
            for fragment in required:
                self.assertIn(fragment, text, f"{readme_name} missing HD cleanup guidance: {fragment}")

    def test_audio_processing_docs_and_dependencies_are_explicit(self) -> None:
        for readme_name in ("README.md", "README.zh-CN.md"):
            text = (ROOT / readme_name).read_text(encoding="utf-8")
            for fragment in ("forge-text-audio", "Stable Audio 3", "small-sfx", "FFmpeg", "FFprobe", "WAV", "AudioClip", "stable-audio-3"):
                self.assertIn(fragment, text, f"{readme_name} missing audio setup guidance: {fragment}")
        self.assertIn("license acceptance", (ROOT / "README.md").read_text(encoding="utf-8").lower())
        self.assertIn("许可证", (ROOT / "README.zh-CN.md").read_text(encoding="utf-8"))
        for readme_name in ("README.md", "README.zh-CN.md"):
            text = (ROOT / readme_name).read_text(encoding="utf-8")
            self.assertIn("game-visual-forge.local.json", text)
            self.assertIn("provider configure", text)
            self.assertIn("install/stable-audio-3", text)
        base = (ROOT / "pyproject.toml").read_text(encoding="utf-8").split("[project.optional-dependencies]", 1)[0].lower()
        for forbidden in ("stable-audio", "torch", "torchaudio", "ffmpeg", "huggingface"):
            self.assertNotIn(forbidden, base)

    def test_install_guides_are_manual_and_repo_local(self) -> None:
        for agent in ("codex", "claude"):
            guide = (ROOT / "install" / agent / "README.md").read_text(encoding="utf-8")
            self.assertIn("copy", guide.lower())
            self.assertIn("skills", guide.lower())
            self.assertIn("does not install dependencies", guide.lower())
            self.assertTrue("src/" in guide or "full repository" in guide.lower())
            self.assertNotIn("copy each directory under `skills/`", guide.lower())
            self.assertNotIn("curl |", guide.lower())
            self.assertNotIn("invoke-webrequest", guide.lower())

    def test_stable_audio_install_guides_are_bilingual_and_isolated(self) -> None:
        english = (ROOT / "install" / "stable-audio-3" / "README.md").read_text(encoding="utf-8")
        chinese = (ROOT / "install" / "stable-audio-3" / "README.zh-CN.md").read_text(encoding="utf-8")
        for text in (english, chinese):
            for fragment in ("stable-audio-3", "provider configure", "provider show-config", "provider preflight", "game-visual-forge.local.json", "UV_NO_MODIFY_PATH", "HF_HOME", "small-sfx", "license"):
                self.assertIn(fragment, text, fragment)
        self.assertIn("README.zh-CN.md", english)
        self.assertIn("README.md", chinese)

    def test_public_files_contain_no_retired_audio_package_name(self) -> None:
        retired_distribution = "stable-audio" + "-tools"
        retired_module = "stable_audio" + "_tools"
        paths = [ROOT / "README.md", ROOT / "README.zh-CN.md", ROOT / "install", ROOT / "skills", ROOT / "src", ROOT / "tests"]
        for base in paths:
            files = [base] if base.is_file() else [item for item in base.rglob("*") if item.is_file() and item.suffix.lower() in {".md", ".py", ".yaml", ".yml"}]
            for path in files:
                text = path.read_text(encoding="utf-8")
                self.assertNotIn(retired_distribution, text, str(path.relative_to(ROOT)))
                self.assertNotIn(retired_module, text, str(path.relative_to(ROOT)))

    def test_video_processing_docs_and_dependencies_are_explicit(self) -> None:
        for readme_name in ("README.md", "README.zh-CN.md"):
            text = (ROOT / readme_name).read_text(encoding="utf-8")
            for fragment in ("FFmpeg", "FFprobe", "mmx", "dreamina", "MINIMAX_API_KEY", "JIMENG_ACCESS_KEY"):
                self.assertIn(fragment, text, f"{readme_name} missing video setup guidance: {fragment}")
        base = (ROOT / "pyproject.toml").read_text(encoding="utf-8").split("[project.optional-dependencies]", 1)[0].lower()
        self.assertNotIn("minimax", base)
        self.assertNotIn("jimeng", base)

    def test_package_declares_m0_version(self) -> None:
        from game_visual_forge import __version__
        self.assertEqual(__version__, "0.1.0")


if __name__ == "__main__":
    unittest.main()
