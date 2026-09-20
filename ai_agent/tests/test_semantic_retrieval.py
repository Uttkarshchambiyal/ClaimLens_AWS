"""Tests for ClaimLens semantic embeddings and vector similarity retrieval."""
import unittest
from ai_agent.retrieval.chunker import DocumentChunker
from ai_agent.retrieval.embeddings import LocalSemanticEmbedding, VectorStore
from ai_agent.retrieval.semantic_retriever import SemanticRetriever


class TestSemanticRetrieval(unittest.TestCase):
    def setUp(self):
        self.embedding_provider = LocalSemanticEmbedding()
        self.chunker = DocumentChunker()
        self.retriever = SemanticRetriever(embeddings_provider=self.embedding_provider, chunker=self.chunker)

        self.claim_data = {
            "claimId": "CLM-SEMANTIC-1",
            "documents": [
                {
                    "id": "doc_summary_1",
                    "name": "CityCare_discharge_summary.pdf",
                    "type": "DISCHARGE_SUMMARY",
                    "pages": 2,
                    "extractedText": "The patient underwent laparoscopic cholecystectomy on March 12 under general anesthesia. Post-operative recovery was uneventful and patient is discharged on oral medications.",
                },
                {
                    "id": "doc_bill_1",
                    "name": "CityCare_itemized_bill.pdf",
                    "type": "BILL",
                    "pages": 3,
                    "extractedText": "Laparoscopic Cholecystectomy Package (CPT 47562): ₹145,000.00.\nOT Room & Anesthesia: ₹38,000.00.\nRoom rent 3 days: ₹36,000.00.\nTotal Stated Amount: ₹248,500.00.",
                },
            ],
            "findings": [],
        }

    def test_paraphrased_surgery_retrieval(self):
        """Verify that 'What surgery did the patient have?' matches 'laparoscopic cholecystectomy' without exact word match."""
        results = self.retriever.retrieve(
            query="What surgery did the patient have?",
            claim_data=self.claim_data,
            top_k=3,
        )

        self.assertGreater(len(results), 0)
        top_score, top_chunk = results[0]
        self.assertGreater(top_score, 0.20)
        self.assertTrue(
            "cholecystectomy" in top_chunk.text.lower() or "laparoscopic" in top_chunk.text.lower()
        )
        self.assertEqual(top_chunk.document_name, "CityCare_discharge_summary.pdf")

    def test_paraphrased_operation_inquiry(self):
        """Verify that 'Which operation was performed?' matches surgical notes."""
        results = self.retriever.retrieve(
            query="Which operation was performed on the patient?",
            claim_data=self.claim_data,
            top_k=3,
        )

        self.assertGreater(len(results), 0)
        top_score, top_chunk = results[0]
        self.assertIn("cholecystectomy", top_chunk.text.lower())

    def test_claim_isolation_in_vector_store(self):
        """Verify that vector store does not leak chunks across different claim IDs."""
        store = VectorStore(self.embedding_provider)
        chunks_claim_a = self.chunker.chunk_claim_data(self.claim_data)

        claim_b_data = dict(self.claim_data)
        claim_b_data["claimId"] = "CLM-DIFFERENT-99"
        claim_b_data["documents"] = [
            {
                "id": "doc_cardio",
                "name": "Cardiology_report.pdf",
                "type": "SUPPORTING_REPORT",
                "extractedText": "Patient presented with acute myocardial infarction and underwent coronary angioplasty with stent placement.",
            }
        ]
        chunks_claim_b = self.chunker.chunk_claim_data(claim_b_data)

        store.add_chunks(chunks_claim_a)
        store.add_chunks(chunks_claim_b)

        # Search within claim A scope
        results_a = store.search("What cardiac procedure?", claim_id="CLM-SEMANTIC-1")
        # Should not return cardiology chunks belonging to claim B
        for _, chunk in results_a:
            self.assertEqual(chunk.claim_id, "CLM-SEMANTIC-1")
            self.assertNotIn("angioplasty", chunk.text.lower())


if __name__ == "__main__":
    unittest.main()
