"""Chat API endpoint handler for ClaimLens AI Agent."""
from __future__ import annotations

from typing import Any
from ai_agent.agent.claim_agent import ClaimAgent
from ai_agent.sessions.session_manager import SessionManager


def handle_chat_request(
    payload: dict[str, Any],
    session_manager: SessionManager | None = None,
    agent: ClaimAgent | None = None,
    tenant_id: str = "default",
) -> dict[str, Any]:
    """Handle POST /api/ai/chat requests."""
    session_mgr = session_manager or SessionManager()
    ai_agent = agent or ClaimAgent()

    message = payload.get("message")
    if not message or not isinstance(message, str) or not message.strip():
        raise ValueError("Field 'message' is required and must be a non-empty string.")

    session_id = payload.get("session_id")
    claim_id = payload.get("claim_id")
    claim_data = payload.get("claim_data")

    # Retrieve or create session
    session = session_mgr.get_or_create_session(
        session_id=session_id,
        tenant_id=tenant_id,
        claim_id=claim_id,
        claim_data=claim_data,
    )

    # Save user message to session
    session_mgr.add_message(session.session_id, role="user", content=message)

    # Convert session history for context if needed
    history = [
        {"role": m.role, "content": m.content}
        for m in session_mgr.get_history(session.session_id)
    ]

    # Process through agent
    result = ai_agent.process_query(
        user_message=message,
        claim_data=session.claim_data,
        conversation_history=history,
    )

    # Save assistant response to session
    session_mgr.add_message(
        session.session_id,
        role="assistant",
        content=result["answer"],
        sources=result["sources"],
    )

    return {
        "answer": result["answer"],
        "sources": result["sources"],
        "confidence": result.get("confidence"),
        "session_id": session.session_id,
        "claim_id": session.claim_id,
        "is_temporary": session.is_temporary,
    }
