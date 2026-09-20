"""Tests for document uploads, partial failures, and temporary sessions."""
import unittest
from ai_agent.api.upload import handle_upload_request
from ai_agent.sessions.session_manager import SessionManager


class TestUploads(unittest.TestCase):
    def test_upload_registration_in_session(self):
        manager = SessionManager()
        payload = {
            "filename": "CityCare_supplemental.pdf",
            "contentType": "application/pdf",
            "documentType": "SUPPORTING_REPORT",
        }
        result = handle_upload_request(payload, session_manager=manager)

        self.assertEqual(result["status"], "READY")
        self.assertIn("documentId", result)
        self.assertIsNotNone(result["session_id"])

        session = manager.get_or_create_session(result["session_id"])
        self.assertIsNotNone(session.claim_data)
        self.assertEqual(len(session.claim_data["documents"]), 1)
        self.assertEqual(session.claim_data["documents"][0]["name"], "CityCare_supplemental.pdf")

    def test_upload_invalid_content_type_rejected(self):
        manager = SessionManager()
        payload = {
            "filename": "malicious.exe",
            "contentType": "application/x-msdownload",
            "documentType": "SUPPORTING_REPORT",
        }
        with self.assertRaises(ValueError):
            handle_upload_request(payload, session_manager=manager)

    def test_upload_invalid_document_type_rejected(self):
        manager = SessionManager()
        payload = {
            "filename": "bill.pdf",
            "contentType": "application/pdf",
            "documentType": "INVALID_TYPE",
        }
        with self.assertRaises(ValueError):
            handle_upload_request(payload, session_manager=manager)


if __name__ == "__main__":
    unittest.main()
