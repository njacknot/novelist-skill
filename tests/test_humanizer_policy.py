import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class HumanizerPolicyTests(unittest.TestCase):
    def test_generic_humanizer_has_no_project_specific_residue(self):
        source = (ROOT / "scripts" / "text_humanizer.py").read_text(encoding="utf-8")

        self.assertNotIn("宁远", source)
        self.assertNotIn("朱雀", source)

    def test_humanizer_prompt_restores_project_voice_after_cleanup(self):
        source = (ROOT / "scripts" / "text_humanizer.py").read_text(encoding="utf-8")

        self.assertIn("恢复项目声线", source)
        self.assertIn("角色说话方式", source)


if __name__ == "__main__":
    unittest.main()
