import unittest
from tools.evidence_engine import verify_evidence_chain, verify_python_syntax

class EvidenceEngineTests(unittest.TestCase):
    def test_valid_python_is_recorded(self):
        result = verify_python_syntax("answer = 42\n")
        self.assertEqual(result["result"], "PASS")

    def test_evidence_chain_is_valid(self):
        verify_python_syntax("value = 'chain-check'\n")
        result = verify_evidence_chain()
        self.assertEqual(result["status"], "PASS")

if __name__ == "__main__":
    unittest.main()
