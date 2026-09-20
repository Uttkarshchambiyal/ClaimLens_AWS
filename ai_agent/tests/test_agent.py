"""Tests for ClaimLens AI Agent core orchestration."""
import unittest
from ai_agent.agent.claim_agent import ClaimAgent
from ai_agent.models.mock import MockModelProvider


class TestClaimAgent(unittest.TestCase):
    def setUp(self):
        self.mock_claim_data = {
            "id": "anl_test_01",
            "claimId": "CLM-20481",
            "status": "COMPLETED",
            "analysisVersion": 1,
            "reviewPriority": "HIGH",
            "claimedAmountPaise": 24850000,
            "extractionQuality": 94,
            "coverage": 100,
            "documents": [
                {
                    "id": "doc_bill",
                    "name": "CityCare_itemized_bill.pdf",
                    "type": "BILL",
                    "version": 1,
                    "pages": 3,
                    "extractionQuality": 94,
                    "status": "READY",
                },
                {
                    "id": "doc_summary",
                    "name": "CityCare_discharge_summary.pdf",
                    "type": "DISCHARGE_SUMMARY",
                    "version": 1,
                    "pages": 2,
                    "extractionQuality": 96,
                    "status": "READY",
                },
            ],
            "findings": [
                {
                    "id": "fnd_01",
                    "checkId": "CHK_01_INVOICE_TOTAL_MATH",
                    "title": "Invoice total does not reconcile",
                    "summary": "Stated total ₹248,500.00 differs from line item sum ₹241,500.00 by ₹7,000.00.",
                    "status": "FINDING",
                    "priority": "HIGH",
                    "reviewerAction": "OPEN",
                    "evidence": [
                        {
                            "evidenceId": "ev_01",
                            "documentId": "doc_bill",
                            "documentName": "CityCare_itemized_bill.pdf",
                            "page": 3,
                            "confidence": 98.4,
                            "excerpt": "Invoice Total ₹248,500.00",
                        }
                    ],
                }
            ],
            "corrections": [],
            "activity": [],
        }

    def test_agent_initialization(self):
        agent = ClaimAgent(model_provider=MockModelProvider())
        self.assertIsNotNone(agent)
        self.assertGreaterEqual(len(agent.tools), 7)

    def test_agent_answers_discrepancy_query_with_sources(self):
        agent = ClaimAgent(model_provider=MockModelProvider())
        response = agent.process_query(
            "What are the discrepancies in this claim?",
            claim_data=self.mock_claim_data,
        )

        self.assertEqual(response["status"], "COMPLETED")
        self.assertIn("answer", response)
        self.assertGreater(len(response["sources"]), 0)
        self.assertTrue(any(s["documentName"] == "CityCare_itemized_bill.pdf" for s in response["sources"]))
        self.assertTrue("₹7,000" in response["answer"] or "248,500" in response["answer"])

    def test_agent_general_terminology_question_without_claim(self):
        agent = ClaimAgent(model_provider=MockModelProvider())
        response = agent.process_query("What is an itemized medical bill?", claim_data=None)

        self.assertEqual(response["status"], "COMPLETED")
        self.assertIn("itemized", response["answer"].lower())
        self.assertEqual(len(response["sources"]), 0)


if __name__ == "__main__":
    unittest.main()
