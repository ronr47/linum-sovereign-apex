import unittest

from core.orchestrator import classify_response


class TrustClassificationTests(unittest.TestCase):

    def test_valid_python_is_not_promoted_by_syntax_only(self):
        status, evidence = classify_response(
            "```python\nanswer = 42\n```"
        )

        self.assertEqual(status, "UNVERIFIED")
        self.assertIn("python_ast_parse", evidence["checks"])
        self.assertTrue(evidence["limitations"])

    def test_invalid_python_is_rejected(self):
        status, evidence = classify_response(
            "```python\ndef broken(:\n```"
        )

        self.assertEqual(status, "REJECTED")
        self.assertTrue(evidence["errors"])

    def test_plain_text_is_unverified(self):
        status, _ = classify_response("The answer is 42.")

        self.assertEqual(status, "UNVERIFIED")

    def test_unknown_language_is_unverified(self):
        status, _ = classify_response(
            "```unknown_language\nsome content\n```"
        )

        self.assertEqual(status, "UNVERIFIED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
