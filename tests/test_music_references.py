from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "skills" / "forge-game-music" / "references"


class MusicReferenceTests(unittest.TestCase):
    def test_reference_set_exists_and_declares_provenance(self):
        names = {
            "prompt-guide.md",
            "game-music-templates.md",
            "comfyui-music3.md",
            "suno-api.md",
            "stable-audio-api.md",
            "processing-and-quality.md",
        }
        self.assertEqual({p.name for p in REF.glob("*.md")}, names)
        for name in names:
            text = (REF / name).read_text(encoding="utf-8")
            self.assertIn("## Sources", text, name)
            self.assertIn("verified", text.lower(), name)

    def test_suno_reference_keeps_unknowns_explicit(self):
        text = (REF / "suno-api.md").read_text(encoding="utf-8")
        self.assertIn("needs_user_action", text)
        self.assertIn("unknown", text.lower())
        self.assertNotIn("make_instrumental", text)
        self.assertNotIn("suno-api.io", text)

    def test_stable_audio_reference_is_three_point_oh(self):
        text = (REF / "stable-audio-api.md").read_text(encoding="utf-8")
        self.assertIn("stable-audio-3", text)
        self.assertIn("1 to 380", text)
        self.assertIn("202", text)
        self.assertNotIn("190 seconds", text)


if __name__ == "__main__":
    unittest.main()
