"""Comprehensive test suite for question-first answering, semantic grounding, and financial precision."""
import unittest
from ai_agent.agent.claim_agent import ClaimAgent
from ai_agent.models.mock import MockModelProvider


class TestQuestionAnswering(unittest.TestCase):
    def setUp(self):
        self.agent = ClaimAgent(model_provider=MockModelProvider())
        self.mock_claim_data = {
            "id": "anl_demo_7J3K",
            "claimId": "CLM-20481",
            "status": "COMPLETED",
            "reviewPriority": "HIGH",
            "claimedAmountPaise": 24850000,
            "documents": [
                {
                    "id": "doc_bill",
                    "name": "CityCare_itemized_bill.pdf",
                    "type": "BILL",
                    "pages": 3,
                    "extractedText": "Invoice Total: ₹248,500.00\nLine Items Sum: ₹241,500.00\nLaparoscopic Cholecystectomy Package (CPT 47562): ₹145,000.00\nOT & Anesthesia: ₹38,000.00\nRoom charges: ₹36,000.00\nPharmacy: ₹22,500.00",
                },
                {
                    "id": "doc_summary",
                    "name": "CityCare_discharge_summary.pdf",
                    "type": "DISCHARGE_SUMMARY",
                    "pages": 2,
                    "extractedText": "Discharge Summary: Patient admitted with symptomatic cholelithiasis. Underwent Laparoscopic Cholecystectomy under general anesthesia on March 12.",
                },
                {
                    "id": "doc_report",
                    "name": "CityCare_lab_report.pdf",
                    "type": "SUPPORTING_REPORT",
                    "pages": 1,
                    "extractedText": "Ultrasound Abdomen: Calculi in gallbladder lumen with wall thickening.",
                },
            ],
            "findings": [
                {
                    "id": "f_total",
                    "checkId": "CHK_01_INVOICE_TOTAL_MATH",
                    "title": "Invoice total does not reconcile",
                    "summary": "Line items sum to ₹241,500.00, which is ₹7,000.00 below stated total ₹248,500.00.",
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

    def test_case_1_amount_question_answers_directly_without_generic_overview(self):
        """Test 1 — Amount: 'What is the final amount?' returns ₹248,500.00 and Page 3 source."""
        response = self.agent.process_query(
            "WHAT IS THE FINAL AMOUNT",
            claim_data=self.mock_claim_data,
        )

        self.assertEqual(response["status"], "COMPLETED")
        # Must contain the exact final amount
        self.assertTrue("248,500" in response["answer"] or "₹248,500.00" in response["answer"])
        # Must cite the bill on Page 3
        self.assertTrue(any(s["documentName"] == "CityCare_itemized_bill.pdf" and s["page"] == 3 for s in response["sources"]))
        # Must NOT contain generic claim overview boilerplate
        self.assertNotIn("I am reviewing claim", response["answer"])
        self.assertNotIn("Ask me about", response["answer"])

    def test_case_2_procedure_question_answers_directly(self):
        """Test 2 — Procedure: 'What surgery did the patient have?' returns Laparoscopic Cholecystectomy."""
        response = self.agent.process_query(
            "What surgery did the patient have?",
            claim_data=self.mock_claim_data,
        )

        self.assertEqual(response["status"], "COMPLETED")
        self.assertIn("Laparoscopic Cholecystectomy", response["answer"])
        self.assertTrue(any("discharge_summary" in s["documentName"].lower() for s in response["sources"]))
        self.assertNotIn("I am reviewing claim", response["answer"])
        self.assertNotIn("Ask me about", response["answer"])

    def test_case_3_paraphrased_procedure_question(self):
        """Test 3 — Paraphrase: 'What operation did the patient undergo?' matches via semantic retrieval."""
        response = self.agent.process_query(
            "What operation did the patient undergo?",
            claim_data=self.mock_claim_data,
        )

        self.assertEqual(response["status"], "COMPLETED")
        self.assertIn("Laparoscopic Cholecystectomy", response["answer"])

    def test_case_4_multi_turn_follow_up(self):
        """Test 4 — Follow-up: 'When was it performed?' resolves antecedent surgery context."""
        history = [
            {"role": "user", "content": "What procedure was performed?"},
            {"role": "assistant", "content": "The patient underwent Laparoscopic Cholecystectomy [Doc: CityCare_discharge_summary.pdf, Page: 1]."},
        ]
        response = self.agent.process_query(
            "When was it performed?",
            claim_data=self.mock_claim_data,
            conversation_history=history,
        )

        self.assertEqual(response["status"], "COMPLETED")
        self.assertIn("March 12", response["answer"])
        self.assertTrue(any("discharge_summary" in s["documentName"].lower() for s in response["sources"]))

    def test_case_5_missing_data_refusal(self):
        """Test 5 — Missing data: 'What was the patient's allergy?' when no allergy data exists."""
        response = self.agent.process_query(
            "What was the patient's allergy?",
            claim_data=self.mock_claim_data,
        )

        self.assertEqual(response["status"], "COMPLETED")
        self.assertIn("I don't have enough evidence in the current claim data to answer that", response["answer"])

    def test_case_6_multi_document_comparison(self):
        """Test 6 — Document comparison: 'Does the billed procedure appear in the discharge summary?'"""
        response = self.agent.process_query(
            "Does the billed procedure appear in the discharge summary?",
            claim_data=self.mock_claim_data,
        )

        self.assertEqual(response["status"], "COMPLETED")
        doc_names = {s["documentName"] for s in response["sources"]}
        self.assertTrue(any("discharge_summary" in d.lower() for d in doc_names))
        self.assertTrue(any("itemized_bill" in d.lower() for d in doc_names))

    def test_case_7_unrelated_information_exclusion(self):
        """Test 7 — Unrelated info: 'What is the final amount?' does not contain generic claim overview."""
        response = self.agent.process_query(
            "What is the final amount?",
            claim_data=self.mock_claim_data,
        )

        # Answer should focus on financial figures, not generic preamble
        self.assertNotIn("I am reviewing claim", response["answer"])
        self.assertNotIn("Ask me about", response["answer"])


if __name__ == "__main__":
    unittest.main()
