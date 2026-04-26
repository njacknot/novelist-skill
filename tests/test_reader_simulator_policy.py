import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "reader_simulator.py"

spec = importlib.util.spec_from_file_location("reader_simulator", SCRIPT)
reader_simulator = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules["reader_simulator"] = reader_simulator
spec.loader.exec_module(reader_simulator)


class ReaderSimulatorPolicyTests(unittest.TestCase):
    def test_sub_2200_chapter_is_not_penalized_for_length_alone(self):
        paragraphs = []
        dialogues = []
        for idx in range(70):
            dialogue = f"我们马上走，这是第{idx}句。"
            dialogues.append(dialogue)
            paragraphs.append(f"“{dialogue}”他说。门外的脚步声又近了一点。")
        content = "\n\n".join(paragraphs)
        word_count = reader_simulator._count_chinese(content)
        ctx = reader_simulator.ChapterContext(
            number=1,
            title="短章",
            file_path=Path("第01章.md"),
            word_count=word_count,
            content=content,
            paragraphs=paragraphs,
            dialogues=dialogues,
            last_paragraph=paragraphs[-1],
        )

        self.assertLess(word_count, 2200)
        self.assertGreaterEqual(reader_simulator.score_retention(ctx), 70)


if __name__ == "__main__":
    unittest.main()
