import unittest
from core.orchestrator import classify_response

class OrchestratorIntegrationTests(unittest.TestCase):
    def test_plain_text_classification(self):
        status, evidence = classify_response("System operational.")
        self.assertEqual(status, "UNVERIFIED")

    def test_valid_python_classification(self):
        status, evidence = classify_response("```python\nx = 42\n```")
        self.assertEqual(status, "UNVERIFIED")
        self.assertEqual(evidence["validator"], "python_ast_parse")
        self.assertEqual(evidence["result"], "PASS")

    def test_invalid_python_classification(self):
        status, evidence = classify_response("```python\ndef broken(:\n```")
        self.assertEqual(status, "REJECTED")
        self.assertEqual(evidence["result"], "FAIL")

if __name__ == "__main__":
    unittest.main()
