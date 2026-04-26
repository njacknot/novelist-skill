import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_chapter_wordcount.py"

spec = importlib.util.spec_from_file_location("check_chapter_wordcount", SCRIPT)
wordcount = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules["check_chapter_wordcount"] = wordcount
spec.loader.exec_module(wordcount)


class WordCountPolicyTests(unittest.TestCase):
    def test_default_policy_reports_short_chapter_without_failing_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            chapter = Path(tmp) / "第01章.md"
            chapter.write_text("# 第01章\n\n短短一章，也可以成立。\n", encoding="utf-8")

            result = wordcount.check_chapter(str(chapter))

        self.assertEqual(result["status"], "pass")
        self.assertIsNone(result["min_words"])

    def test_explicit_minimum_still_fails_when_requested(self):
        with tempfile.TemporaryDirectory() as tmp:
            chapter = Path(tmp) / "第01章.md"
            chapter.write_text("# 第01章\n\n短短一章。\n", encoding="utf-8")

            result = wordcount.check_chapter(str(chapter), min_words=50)

        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["min_words"], 50)


if __name__ == "__main__":
    unittest.main()
