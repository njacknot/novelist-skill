import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "chapter_gate_check.py"

spec = importlib.util.spec_from_file_location("chapter_gate_check", SCRIPT)
chapter_gate_check = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules["chapter_gate_check"] = chapter_gate_check
spec.loader.exec_module(chapter_gate_check)


VALID_CARD = """# 第 001 章 · 控制卡

## 章节身份

第 001 章：雨夜来信。

## 本章任务

让主角收到旧案线索，但不能立刻破案。

## 回忆与回收压力

回收上一章的人情债，保留车票谜团。

## 冲突设计

主角想查信，搭档坚持先保全证据。

## 角色使用

主角主动追问，搭档隐瞒一段旧关系。

## 伏笔与禁止揭露

只能露出车票，不揭露寄信人身份。

## 场景单元

1. 雨夜收信。
2. 证物争执。
3. 车票露出。

## 文风/去 AI 任务

用现场动作和对白承压，避免抽象总结。

## 风险扫描

不使用论文式解释，不让主角直接说破答案。

## 章末钩子

信封里夹着一张十年前的车票。
"""


class ChapterGateControlCardTests(unittest.TestCase):
    def _project(self, tmp: str, with_card: bool) -> tuple[Path, Path]:
        root = Path(tmp)
        chapter_dir = root / "03_manuscript"
        artifact_dir = root / "04_editing" / "gate_artifacts" / "ch001"
        card_dir = root / "04_editing" / "control_cards"
        chapter_dir.mkdir(parents=True)
        artifact_dir.mkdir(parents=True)
        if with_card:
            card_dir.mkdir(parents=True)
            (card_dir / "ch001-control-card.md").write_text(VALID_CARD, encoding="utf-8")

        chapter = chapter_dir / "第001章-雨夜来信.md"
        chapter.write_text(
            "# 第001章 雨夜来信\n\n"
            "雨水敲在窗台上。林照把信封压在台灯下，指腹擦过潮湿的邮戳。\n\n"
            "“先别拆。”周岚把证物袋推过来，“你知道这封信会把谁拖回来。”\n\n"
            "林照没有抬头，只把封口沿着旧折痕慢慢撕开。里面掉出一张车票，日期停在十年前。\n",
            encoding="utf-8",
        )
        (root / "02-写作计划.json").write_text(
            json.dumps(
                {
                    "minWordsPerChapter": 0,
                    "gateThresholds": {"reader": 70},
                    "chapters": [{"chapterNumber": 1, "title": "雨夜来信", "status": "draft"}],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        for name in [
            "memory_update.md",
            "consistency_report.md",
            "style_calibration.md",
            "copyedit_report.md",
            "publish_ready.md",
        ]:
            (artifact_dir / name).write_text(f"# {name}\n\n已完成。\n", encoding="utf-8")
        (artifact_dir / "reader_report.md").write_text("总分：80 / 100\n", encoding="utf-8")
        return root, chapter

    def test_gate_fails_when_control_card_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, chapter = self._project(tmp, with_card=False)

            result, _plan, _out = chapter_gate_check.run_gate(root, chapter, 1)

        self.assertFalse(result["passed"])
        self.assertIn("control_card_failed", result["fail_reason"])
        self.assertFalse(result["dimensions"]["control_card"]["passed"])

    def test_gate_passes_when_control_card_and_artifacts_are_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, chapter = self._project(tmp, with_card=True)

            result, plan, _out = chapter_gate_check.run_gate(root, chapter, 1)

        self.assertTrue(result["passed"])
        self.assertTrue(result["dimensions"]["control_card"]["passed"])
        self.assertEqual(plan["chapters"][0]["status"], "completed")

    def _fanqie_project(self, tmp: str, opening: str) -> tuple[Path, Path]:
        root = Path(tmp)
        chapter_dir = root / "03_manuscript"
        card_dir = root / "04_editing" / "control_cards"
        memory_dir = root / "00_memory"
        chapter_dir.mkdir(parents=True)
        card_dir.mkdir(parents=True)
        memory_dir.mkdir(parents=True)
        (card_dir / "ch001-control-card.md").write_text(VALID_CARD, encoding="utf-8")
        (memory_dir / "novel_state.md").write_text(
            "# 动态状态\n\n第001章：林照收到十年前车票，旧案线索启动。\n",
            encoding="utf-8",
        )
        chapter = chapter_dir / "第001章-雨夜来信.md"
        chapter.write_text(
            "# 第001章 雨夜来信\n\n"
            f"{opening}\n\n"
            "“先别拆。”周岚把证物袋推过来，“你知道这封信会把谁拖回来。”\n\n"
            "林照沿着旧折痕撕开封口。里面掉出一张车票，日期停在十年前。\n"
            "窗外忽然响起敲门声，可这个点，楼道监控早就坏了。\n",
            encoding="utf-8",
        )
        (root / "02-写作计划.json").write_text(
            json.dumps(
                {
                    "platform": "fanqie",
                    "writingMode": "serial",
                    "minWordsPerChapter": 0,
                    "gateThresholds": {"reader": 70},
                    "chapters": [
                        {
                            "chapterNumber": 1,
                            "title": "雨夜来信",
                            "goal": "让主角收到旧案线索，但不能立刻破案。",
                            "status": "draft",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return root, chapter

    def test_fanqie_gate_uses_light_dimensions_and_reader_is_advisory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, chapter = self._fanqie_project(
                tmp,
                "雨水砸在窗台上时，林照看见信封角落的血印。寄件人一栏空着，邮戳却来自十年前。",
            )

            result, plan, _out = chapter_gate_check.run_gate(root, chapter, 1)

        self.assertTrue(result["passed"])
        self.assertEqual(result["gate_mode"], "fanqie")
        self.assertIn("fanqie_opening", result["dimensions"])
        self.assertNotIn("memory", result["dimensions"])
        self.assertTrue(result["dimensions"]["reader"]["advisory"])
        self.assertTrue(result["dimensions"]["reader"]["passed"])
        self.assertEqual(plan["chapters"][0]["status"], "completed")

    def test_fanqie_gate_fails_when_opening_lacks_hook(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, chapter = self._fanqie_project(
                tmp,
                "清晨的阳光很好，城市慢慢醒来。林照坐在桌前，觉得今天和平时没有什么区别。",
            )

            result, _plan, _out = chapter_gate_check.run_gate(root, chapter, 1)

        self.assertFalse(result["passed"])
        self.assertIn("fanqie_opening_failed", result["fail_reason"])


if __name__ == "__main__":
    unittest.main()
