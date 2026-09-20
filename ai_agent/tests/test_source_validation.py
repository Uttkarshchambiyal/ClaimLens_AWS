"""Tests for source validation and citation filtering."""
import unittest
from ai_agent.retrieval.source_validator import SourceValidator


class TestSourceValidation(unittest.TestCase):
    def setUp(self):
        self.sample_claim = {
            "id": "anl_01",
            "documents": [
                {"id": "doc_1", "name": "real_bill.pdf"},
                {"id": "doc_2", "name": "real_summary.pdf"},
            ],
            "findings": [
                {
                    "id": "f_1",
                    "evidence": [
                        {
                            "evidenceId": "ev_real_1",
                            "documentId": "doc_1",
                            "documentName": "real_bill.pdf",
                            "page": 2,
                            "confidence": 99.0,
                            "excerpt": "Total ₹5000",
                        }
                    ],
                }
            ],
        }

    def test_validates_genuine_citations(self):
        validator = SourceValidator()
        candidate_sources = [
            {"documentName": "real_bill.pdf", "page": 2},
            {"evidenceId": "ev_real_1"},
        ]
        validated = validator.validate_sources(candidate_sources, self.sample_claim)

        self.assertEqual(len(validated), 2)
        self.assertEqual(validated[0]["documentName"], "real_bill.pdf")
        self.assertEqual(validated[1]["evidenceId"], "ev_real_1")

    def test_rejects_hallucinated_citations(self):
        validator = SourceValidator()
        candidate_sources = [
            {"documentName": "fake_secret_report.pdf", "page": 99},
            {"evidenceId": "ev_non_existent_999"},
        ]
        validated = validator.validate_sources(candidate_sources, self.sample_claim)

        self.assertEqual(len(validated), 0)

    def test_extracts_and_sanitizes_text_citations(self):
        validator = SourceValidator()
        text = "Based on [Doc: real_bill.pdf, Page: 2] and [Doc: fake_doc.pdf, Page: 10], the charges align."
        cleaned_text, valid_sources = validator.extract_and_validate_citations_from_text(text, self.sample_claim)

        self.assertEqual(len(valid_sources), 1)
        self.assertEqual(valid_sources[0]["documentName"], "real_bill.pdf")


if __name__ == "__main__":
    unittest.main()
