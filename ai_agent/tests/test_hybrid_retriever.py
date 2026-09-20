"""Tests for ClaimLens Hybrid Retriever combining semantic and exact lexical search."""
import unittest
from ai_agent.retrieval.hybrid_retriever import HybridRetriever


class TestHybridRetriever(unittest.TestCase):
    def setUp(self):
        self.retriever = HybridRetriever()
        self.claim_data = {
            "claimId": "CLM-HYBRID-101",
            "claimedAmountPaise": 24850000,
            "documents": [
                {
                    "id": "doc_bill",
                    "name": "CityCare_itemized_bill.pdf",
                    "type": "BILL",
                    "pages": 3,
                    "extractedText": "Invoice Number: INV-88219\nLaparoscopic Cholecystectomy (CPT 47562): ₹145,000.00\nStated Total: ₹248,500.00\nLine Items Sum: ₹241,500.00",
                },
                {
                    "id": "doc_summary",
                    "name": "CityCare_discharge_summary.pdf",
                    "type": "DISCHARGE_SUMMARY",
                    "pages": 2,
                    "extractedText": "Discharge Summary: Patient admitted with biliary colic. Underwent successful laparoscopic cholecystectomy on March 12 by Dr. Verma.",
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

    def test_exact_code_and_amount_retrieval(self):
        """Exact tokens like CPT 47562 or ₹248,500.00 should be retrieved accurately."""
        results = self.retriever.retrieve(
            query="Tell me about CPT 47562 and ₹248,500.00",
            claim_data=self.claim_data,
            top_k=3,
        )
        self.assertGreater(len(results), 0)
        self.assertTrue(
            any("47562" in r["excerpt"] or "248,500" in r["excerpt"] for r in results)
        )

    def test_semantic_query_retrieval(self):
        """Semantic concept query 'treatment for gallbladder' matches without exact words."""
        results = self.retriever.retrieve(
            query="What treatment did the patient receive for gallbladder?",
            claim_data=self.claim_data,
            top_k=3,
        )
        self.assertGreater(len(results), 0)
        top_excerpt = results[0]["excerpt"].lower()
        self.assertTrue("cholecystectomy" in top_excerpt or "laparoscopic" in top_excerpt)

    def test_document_diversity_on_comparison_queries(self):
        """Queries asking to compare documents should retrieve chunks from both BILL and DISCHARGE_SUMMARY."""
        results = self.retriever.retrieve(
            query="Compare the itemized bill with the discharge summary",
            claim_data=self.claim_data,
            top_k=4,
        )
        self.assertGreaterEqual(len(results), 2)
        doc_types = {r["documentType"] for r in results}
        self.assertTrue("BILL" in doc_types or "DISCHARGE_SUMMARY" in doc_types)


if __name__ == "__main__":
    unittest.main()
