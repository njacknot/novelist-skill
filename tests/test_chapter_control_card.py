import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "chapter_control_card.py"

spec = importlib.util.spec_from_file_location("chapter_control_card", SCRIPT)
chapter_control_card = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules["chapter_control_card"] = chapter_control_card
spec.loader.exec_module(chapter_control_card)


class ChapterControlCardTests(unittest.TestCase):
    def _project(self, tmp: str) -> Path:
        root = Path(tmp)
        (root / "00_memory").mkdir()
        (root / "00_memory" / "novel_state.md").write_text(
            "# 动态状态\n\n主角欠下的人情尚未归还。\n",
            encoding="utf-8",
        )
        (root / "02-写作计划.json").write_text(
            json.dumps(
                {
                    "chapters": [
                        {
                            "chapterNumber": 1,
                            "title": "雨夜来信",
                            "goal": "让主角收到旧案线索，但不能立刻破案。",
                            "hook": "信封里夹着一张十年前的车票。",
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return root

    def test_generate_card_writes_default_path_with_required_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(tmp)

            card_path = chapter_control_card.generate_card(root, 1)
            validation = chapter_control_card.validate_card(card_path)
            text = card_path.read_text(encoding="utf-8")

            self.assertEqual(card_path.name, "ch001-control-card.md")
            self.assertIn("04_editing/control_cards", card_path.as_posix())
            self.assertTrue(validation["passed"])
            self.assertIn("## 本章任务", text)
            self.assertIn("让主角收到旧案线索", text)
            self.assertIn("## 章末钩子", text)

    def test_validate_card_fails_when_required_sections_are_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            card = Path(tmp) / "card.md"
            card.write_text("# 控制卡\n\n## 本章任务\n\n只写了一个小节。\n", encoding="utf-8")

            validation = chapter_control_card.validate_card(card)

        self.assertFalse(validation["passed"])
        self.assertIn("回忆与回收压力", validation["missing_sections"])


if __name__ == "__main__":
    unittest.main()
