import unittest

from audit import audit, markdown
from test_rank import fixture


class AuditTests(unittest.TestCase):
    def test_audit_without_foreign_events_keeps_documented_override_visible(self):
        result = audit(fixture(), {"playerOverrides": {"1": "PR 2025"}})
        self.assertEqual(result["counts"]["eligibleEvents"], 2)
        self.assertEqual(result["coverage"]["top100WithUnverifiedCountry"], 1)
        self.assertEqual(result["unverifiedCountry"][0]["tag"], "P1")
        self.assertEqual(result["top10Sensitivity"][0]["scenarios"], {})
        self.assertIn("Candidaturas del top 100", markdown(result))


if __name__ == "__main__":
    unittest.main()
