"""Tests for multi-document comparison queries across bills, discharge summaries, and lab reports."""
import unittest
from ai_agent.agent.claim_agent import ClaimAgent
from ai_agent.models.mock import MockModelProvider


class TestMultiDocComparison(unittest.TestCase):
    def setUp(self):
        self.agent = ClaimAgent(model_provider=MockModelProvider())
        self.claim_data = {
            "claimId": "CLM-COMPARE-303",
            "documents": [
                {
                    "id": "doc_summary",
                    "name": "CityCare_discharge_summary.pdf",
                    "type": "DISCHARGE_SUMMARY",
                    "pages": 2,
                    "extractedText": "Patient underwent Laparoscopic Cholecystectomy under general anesthesia on March 12.",
                },
                {
                    "id": "doc_bill",
                    "name": "CityCare_itemized_bill.pdf",
                    "type": "BILL",
                    "pages": 3,
                    "extractedText": "Laparoscopic Cholecystectomy Package (CPT 47562): ₹145,000.00. Stated Total: ₹248,500.00. Sum: ₹241,500.00.",
                },
                {
                    "id": "doc_lab",
                    "name": "CityCare_lab_report.pdf",
                    "type": "SUPPORTING_REPORT",
                    "pages": 1,
                    "extractedText": "Ultrasound Abdomen: Multiple gallstones within thickened gallbladder wall. Consistent with cholelithiasis.",
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
                            "excerpt": "Stated Total: ₹248,500.00 vs Sum: ₹241,500.00",
                        }
                    ],
                }
            ],
        }

    def test_multi_document_comparison_response(self):
        """Verify comparison query synthesizes across files and cites both documents."""
        response = self.agent.process_query(
            user_message="Compare the itemized bill with the discharge summary",
            claim_data=self.claim_data,
        )

        self.assertEqual(response["status"], "COMPLETED")
        self.assertIn("Comparison", response["answer"])
        self.assertIn("Discharge Summary", response["answer"])
        self.assertIn("Itemized Bill", response["answer"])

        doc_names = {s["documentName"] for s in response["sources"]}
        self.assertIn("CityCare_discharge_summary.pdf", doc_names)
        self.assertIn("CityCare_itemized_bill.pdf", doc_names)

    def test_strict_missing_evidence_refusal(self):
        """Verify that asking claim-specific questions when claim_data is None produces explicit refusal."""
        response = self.agent.process_query(
            user_message="What surgery did the patient have?",
            claim_data=None,
        )

        self.assertEqual(response["status"], "COMPLETED")
        self.assertIn("I don't have enough evidence in the current claim data", response["answer"])
        self.assertEqual(len(response["sources"]), 0)


if __name__ == "__main__":
    unittest.main()
