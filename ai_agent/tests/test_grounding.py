"""Tests for evidence grounding and refusal to fabricate claims without evidence."""
import unittest
from ai_agent.agent.claim_agent import ClaimAgent
from ai_agent.models.mock import MockModelProvider


class TestGrounding(unittest.TestCase):
    def test_refuses_to_fabricate_claim_details_when_no_context(self):
        agent = ClaimAgent(model_provider=MockModelProvider())
        response = agent.process_query("Was this patient's surgery medically necessary?", claim_data=None)

        self.assertIn("don't have enough evidence", response["answer"].lower())
        self.assertIn("upload", response["answer"].lower())
        self.assertEqual(len(response["sources"]), 0)

    def test_refuses_to_fabricate_unrelated_findings(self):
        agent = ClaimAgent(model_provider=MockModelProvider())
        claim_data = {
            "id": "anl_empty",
            "claimId": "CLM-EMPTY",
            "status": "PROCESSING",
            "documents": [],
            "findings": [],
        }
        response = agent.process_query("What was the patient's heart rate in the ICU?", claim_data=claim_data)

        self.assertEqual(len(response["sources"]), 0)

    def test_answers_general_knowledge_correctly(self):
        agent = ClaimAgent(model_provider=MockModelProvider())
        response = agent.process_query("What is a discharge summary?", claim_data=None)

        self.assertIn("discharge summary", response["answer"].lower())
        self.assertTrue("clinical" in response["answer"].lower() or "hospital" in response["answer"].lower())


if __name__ == "__main__":
    unittest.main()
