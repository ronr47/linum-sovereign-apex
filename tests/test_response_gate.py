import unittest

from tools.response_gate import verify_candidate, verify_python


class ResponseGateTests(unittest.TestCase):
    def test_valid_python(self):
        result = verify_python("answer = 40 + 2")
        self.assertEqual(result["status"], "PASS")

    def test_invalid_python(self):
        result = verify_python("def broken(:")
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(result["errors"])

    def test_python_fence(self):
        result = verify_candidate(
            "```python\nanswer = 42\n```", "python"
        )
        self.assertEqual(result["status"], "PASS")

    def test_unknown_language_is_not_passed(self):
        result = verify_candidate("some code", "unknown")
        self.assertEqual(result["status"], "UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
