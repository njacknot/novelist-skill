import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CommandContractIntegrityTests(unittest.TestCase):
    def test_referenced_python_scripts_exist(self):
        contracts = ROOT / "references" / "advanced" / "command-contracts.md"
        text = contracts.read_text(encoding="utf-8")

        refs = sorted(set(re.findall(r"scripts/([\w_]+\.py)", text)))
        missing = [ref for ref in refs if not (ROOT / "scripts" / ref).exists()]

        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
