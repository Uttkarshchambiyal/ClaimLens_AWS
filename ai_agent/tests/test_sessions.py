"""Tests for session manager, memory scoping, and tenant/claim isolation."""
import unittest
from ai_agent.sessions.session_manager import SessionManager


class TestSessions(unittest.TestCase):
    def test_session_creation_and_message_history(self):
        manager = SessionManager(ttl_seconds=3600)
        session = manager.get_or_create_session(
            session_id="sess_01",
            tenant_id="tenant_a",
            claim_id="CLM-100",
        )

        self.assertEqual(session.session_id, "sess_01")
        self.assertEqual(session.claim_id, "CLM-100")

        manager.add_message("sess_01", "user", "Hello assistant")
        manager.add_message("sess_01", "assistant", "Hello reviewer", sources=[{"doc": "test.pdf"}])

        history = manager.get_history("sess_01")
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].role, "user")
        self.assertEqual(history[0].content, "Hello assistant")
        self.assertEqual(history[1].role, "assistant")
        self.assertEqual(len(history[1].sources), 1)

    def test_tenant_isolation_blocks_cross_tenant_access(self):
        manager = SessionManager()
        manager.get_or_create_session(
            session_id="sess_secret",
            tenant_id="tenant_a",
            claim_id="CLM-A",
        )

        # Attempt to access session with another tenant must raise PermissionError
        with self.assertRaises(PermissionError):
            manager.get_or_create_session(
                session_id="sess_secret",
                tenant_id="tenant_b",
            )

    def test_temporary_session_flag(self):
        manager = SessionManager()
        session = manager.get_or_create_session(session_id="temp_sess", claim_id=None)
        self.assertTrue(session.is_temporary)

        claim_session = manager.get_or_create_session(session_id="claim_sess", claim_id="CLM-999")
        self.assertFalse(claim_session.is_temporary)


if __name__ == "__main__":
    unittest.main()
