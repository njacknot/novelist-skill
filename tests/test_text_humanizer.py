import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "text_humanizer.py"


spec = importlib.util.spec_from_file_location("text_humanizer", SCRIPT)
text_humanizer = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules["text_humanizer"] = text_humanizer
spec.loader.exec_module(text_humanizer)


class TextHumanizerRiskTests(unittest.TestCase):
    def test_single_fatal_template_warns_instead_of_failing(self):
        detector = text_humanizer.RiskDetector()
        with tempfile.TemporaryDirectory() as tmp:
            chapter = Path(tmp) / "第01章.md"
            chapter.write_text("# 第01章\n\n他的声音很平静。\n", encoding="utf-8")
            report = detector.detect_file(chapter)

        self.assertEqual(report.gate_status, "warn")
        self.assertGreater(report.ai_risk_score, 0)
        self.assertEqual(report.category_hits["致命模板"], 1)

    def test_repeated_fatal_templates_fail_gate(self):
        detector = text_humanizer.RiskDetector()
        with tempfile.TemporaryDirectory() as tmp:
            chapter = Path(tmp) / "第01章.md"
            chapter.write_text("# 第01章\n\n他的声音很平静。\n\n他没有回答。\n", encoding="utf-8")
            report = detector.detect_file(chapter)

        self.assertEqual(report.gate_status, "fail")
        self.assertGreater(report.ai_risk_score, 0)
        self.assertEqual(report.category_hits["致命模板"], 2)

    def test_advisory_items_do_not_accumulate_into_failure(self):
        detector = text_humanizer.RiskDetector(min_hanzi=5000)
        with tempfile.TemporaryDirectory() as tmp:
            chapter = Path(tmp) / "第01章.md"
            chapter.write_text(
                "# 第01章\n\n"
                "他很清楚，今天不能退。\n\n"
                "这意味着，所有人都在等结果。\n\n"
                "这说明，旧办法已经不管用了。\n",
                encoding="utf-8",
            )
            report = detector.detect_file(chapter)

        self.assertEqual(report.gate_status, "warn")
        self.assertGreaterEqual(report.scores["advisory"], 19)
        self.assertEqual(report.scores["hard_fail"], 0)

    def test_broken_quote_rule_does_not_flag_quoted_term(self):
        detector = text_humanizer.RiskDetector()
        with tempfile.TemporaryDirectory() as tmp:
            chapter = Path(tmp) / "第02章.md"
            chapter.write_text("# 第02章\n\n她\"解释\"这两个字被弹幕刷屏。\n", encoding="utf-8")
            report = detector.detect_file(chapter)

        self.assertEqual(report.gate_status, "pass")
        self.assertFalse(any(issue.rule_id == "artifact.broken_quote.pronoun" for issue in report.issues))

    def test_risk_cli_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            chapter = Path(tmp) / "第03章.md"
            chapter.write_text("# 第03章\n\n他的声音很平静。\n\n他没有回答。\n", encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "risk", str(chapter), "-f", "json"],
                check=True,
                capture_output=True,
                text=True,
            )

        payload = json.loads(proc.stdout)
        self.assertEqual(payload["summary"]["chapter_count"], 1)
        self.assertEqual(payload["summary"]["fail_count"], 1)
        self.assertEqual(payload["chapters"][0]["gate_status"], "fail")

    def test_generic_broken_quote_name_is_critical(self):
        detector = text_humanizer.RiskDetector()
        with tempfile.TemporaryDirectory() as tmp:
            chapter = Path(tmp) / "第04章.md"
            chapter.write_text("# 第04章\n\n\"刘明，\"许雯\"不是一个人。\"\n", encoding="utf-8")
            report = detector.detect_file(chapter)

        self.assertEqual(report.gate_status, "fail")
        self.assertTrue(any(issue.rule_id == "artifact.broken_quote.name" for issue in report.issues))


if __name__ == "__main__":
    unittest.main()
