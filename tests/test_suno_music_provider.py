import unittest
from tests._bootstrap import ROOT  # noqa: F401
from game_visual_forge.providers.suno_music import preflight, submit, query, download


class SunoProviderTests(unittest.TestCase):
    def test_official_schema_gate_is_explicit(self):
        result = preflight({})
        self.assertEqual(result["status"], "needs_user_action")
        self.assertTrue(result["missing"])
        with self.assertRaisesRegex(RuntimeError, "official"):
            submit({}, lambda *args: None)
        with self.assertRaisesRegex(RuntimeError, "official"):
            query("task", None, lambda *args: None)
        with self.assertRaisesRegex(RuntimeError, "official"):
            download("task", None, None, lambda *args: None)


if __name__ == "__main__": unittest.main()
