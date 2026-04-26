import importlib.util
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "writeback_audit.py"

spec = importlib.util.spec_from_file_location("writeback_audit", SCRIPT)
writeback_audit = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules["writeback_audit"] = writeback_audit
spec.loader.exec_module(writeback_audit)


class WritebackAuditTests(unittest.TestCase):
    def _project(self, tmp: str) -> Path:
        root = Path(tmp)
        (root / "00_memory").mkdir()
        (root / "03_manuscript").mkdir()
        (root / "04_editing" / "control_cards").mkdir(parents=True)
        (root / "00_memory" / "novel_state.md").write_text("# 动态状态\n\n初始。\n", encoding="utf-8")
        (root / "02-写作计划.json").write_text('{"chapters": []}\n', encoding="utf-8")
        return root

    def test_changed_reports_false_when_tracked_files_are_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(tmp)
            before = writeback_audit.snapshot_project(root)

            result = writeback_audit.changed_since(before, root)

        self.assertFalse(result["changed"])
        self.assertEqual(result["changed_files"], [])

    def test_changed_reports_true_when_state_file_is_updated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(tmp)
            before = writeback_audit.snapshot_project(root)
            time.sleep(0.01)
            (root / "00_memory" / "novel_state.md").write_text("# 动态状态\n\n已接受第 1 章。\n", encoding="utf-8")

            result = writeback_audit.changed_since(before, root)

        self.assertTrue(result["changed"])
        self.assertIn("00_memory/novel_state.md", result["changed_files"])


if __name__ == "__main__":
    unittest.main()
