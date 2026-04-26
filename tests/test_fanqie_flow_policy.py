import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fanqie_flow_policy.py"

spec = importlib.util.spec_from_file_location("fanqie_flow_policy", SCRIPT)
fanqie_flow_policy = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules["fanqie_flow_policy"] = fanqie_flow_policy
spec.loader.exec_module(fanqie_flow_policy)


class FanqieFlowPolicyTests(unittest.TestCase):
    def test_fanqie_blocks_parallel_drafting_and_stops_at_opening_checkpoint(self):
        plan = {
            "platform": "fanqie",
            "writingMode": "subagent-parallel",
            "chapters": [
                {"chapterNumber": 1, "status": "completed", "wordCount": 7200},
                {"chapterNumber": 2, "status": "completed", "wordCount": 6900},
                {"chapterNumber": 3, "status": "completed", "wordCount": 7100},
            ],
        }

        result = fanqie_flow_policy.evaluate_plan(plan)

        self.assertFalse(result["can_continue"])
        self.assertIn("subagent_parallel_forbidden", result["issues"])
        self.assertEqual(result["checkpoint"]["id"], "opening_3_chapters")

    def test_fanqie_stops_at_20k_after_opening_review_passes(self):
        plan = {
            "platform": "fanqie",
            "writingMode": "serial",
            "fanqieReviews": {"opening_3_chapters": {"passed": True}},
            "chapters": [
                {"chapterNumber": 1, "status": "completed", "wordCount": 7200},
                {"chapterNumber": 2, "status": "completed", "wordCount": 6900},
                {"chapterNumber": 3, "status": "completed", "wordCount": 7100},
            ],
        }

        result = fanqie_flow_policy.evaluate_plan(plan)

        self.assertFalse(result["can_continue"])
        self.assertEqual(result["checkpoint"]["id"], "signing_20k")


if __name__ == "__main__":
    unittest.main()
