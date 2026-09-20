"""Tests for multi-turn conversational coreference resolution and follow-up reasoning."""
import unittest
from ai_agent.agent.claim_agent import ClaimAgent
from ai_agent.models.mock import MockModelProvider


class TestConversationalFollowUp(unittest.TestCase):
    def setUp(self):
        self.agent = ClaimAgent(model_provider=MockModelProvider())
        self.claim_data = {
            "claimId": "CLM-CONV-202",
            "documents": [
                {
                    "id": "doc_summary",
                    "name": "CityCare_discharge_summary.pdf",
                    "type": "DISCHARGE_SUMMARY",
                    "pages": 2,
                    "extractedText": "The patient underwent laparoscopic cholecystectomy on March 12 by Dr. Sharma. Discharged in stable condition on March 14.",
                },
                {
                    "id": "doc_bill",
                    "name": "CityCare_itemized_bill.pdf",
                    "type": "BILL",
                    "pages": 3,
                    "extractedText": "Laparoscopic Cholecystectomy Package: ₹145,000.00. Total Bill: ₹248,500.00.",
                },
            ],
            "findings": [],
        }

    def test_followup_query_enrichment(self):
        """Verify that pronoun 'it' in 'When was it performed?' resolves to prior surgery context."""
        history = [
            {"role": "user", "content": "What surgery did the patient have?"},
            {"role": "assistant", "content": "The patient underwent Laparoscopic Cholecystectomy [Doc: CityCare_discharge_summary.pdf, Page: 1]."},
        ]

        enriched = self.agent._resolve_conversational_query("When was it performed?", history)
        self.assertIn("Laparoscopic", enriched)
        self.assertIn("Cholecystectomy", enriched)

    def test_multi_turn_flow(self):
        """Verify end-to-end multi-turn query execution with citations."""
        history = [
            {"role": "user", "content": "What surgery did the patient have?"},
            {"role": "assistant", "content": "The patient underwent Laparoscopic Cholecystectomy [Doc: CityCare_discharge_summary.pdf, Page: 1]."},
        ]

        response = self.agent.process_query(
            user_message="When was it performed?",
            claim_data=self.claim_data,
            conversation_history=history,
        )

        self.assertEqual(response["status"], "COMPLETED")
        self.assertIn("March 12", response["answer"])
        self.assertTrue(
            any(s["documentName"] == "CityCare_discharge_summary.pdf" for s in response["sources"])
        )


if __name__ == "__main__":
    unittest.main()
