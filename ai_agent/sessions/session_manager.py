"""Session Manager for ClaimLens AI Agent ensuring strict tenant and claim isolation."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
import time
import uuid
from typing import Any


@dataclass
class ChatMessage:
    role: str  # 'user' | 'assistant' | 'system'
    content: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class AgentSession:
    session_id: str
    tenant_id: str
    claim_id: str | None
    claim_data: dict[str, Any] | None = None
    messages: list[ChatMessage] = field(default_factory=list)
    is_temporary: bool = False
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)


class SessionManager:
    def __init__(self, ttl_seconds: int | None = None):
        self.ttl_seconds = ttl_seconds or int(os.getenv("AI_SESSION_TTL", "86400"))
        self._sessions: dict[str, AgentSession] = {}

    def get_or_create_session(
        self,
        session_id: str | None,
        tenant_id: str = "default",
        claim_id: str | None = None,
        claim_data: dict[str, Any] | None = None,
    ) -> AgentSession:
        self._cleanup_expired()

        if session_id and session_id in self._sessions:
            session = self._sessions[session_id]
            # Verify tenant isolation
            if session.tenant_id != tenant_id:
                raise PermissionError("Access denied to requested session across tenant boundary.")
            # If claim_id changed in the same session, re-scope claim data
            if claim_id and session.claim_id != claim_id:
                session.claim_id = claim_id
                session.claim_data = claim_data
            elif claim_data is not None:
                session.claim_data = claim_data
            session.last_accessed = time.time()
            return session

        new_session_id = session_id or str(uuid.uuid4())
        is_temp = claim_id is None or claim_id.startswith("temp_")
        session = AgentSession(
            session_id=new_session_id,
            tenant_id=tenant_id,
            claim_id=claim_id,
            claim_data=claim_data,
            is_temporary=is_temp,
        )
        self._sessions[new_session_id] = session
        return session

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        sources: list[dict[str, Any]] | None = None,
    ) -> None:
        if session_id not in self._sessions:
            raise KeyError(f"Session {session_id} not found.")
        session = self._sessions[session_id]
        session.messages.append(
            ChatMessage(
                role=role,
                content=content,
                sources=sources or [],
            )
        )
        session.last_accessed = time.time()

    def get_history(self, session_id: str) -> list[ChatMessage]:
        if session_id not in self._sessions:
            return []
        return list(self._sessions[session_id].messages)

    def attach_uploaded_document(
        self,
        session_id: str,
        document_id: str,
        filename: str,
        document_type: str,
        extracted_text: str | None = None,
    ) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if not session:
            session = self.get_or_create_session(session_id=session_id)

        if not session.claim_data:
            session.claim_data = {
                "claimId": f"temp_claim_{session_id[:8]}",
                "status": "PROCESSING",
                "documents": [],
                "findings": [],
                "activity": [],
            }

        doc_record = {
            "id": document_id,
            "name": filename,
            "filename": filename,
            "type": document_type,
            "status": "READY",
            "pages": 1,
            "extractedText": extracted_text or "",
        }
        session.claim_data.setdefault("documents", []).append(doc_record)
        return doc_record

    def _cleanup_expired(self) -> None:
        now = time.time()
        expired = [sid for sid, s in self._sessions.items() if now - s.last_accessed > self.ttl_seconds]
        for sid in expired:
            del self._sessions[sid]
