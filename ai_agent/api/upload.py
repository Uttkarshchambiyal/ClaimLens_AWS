"""Upload API endpoint handler for ClaimLens AI Agent."""
from __future__ import annotations

import uuid
from typing import Any
from ai_agent.sessions.session_manager import SessionManager


def handle_upload_request(
    payload: dict[str, Any],
    session_manager: SessionManager | None = None,
    tenant_id: str = "default",
) -> dict[str, Any]:
    """Handle POST /api/ai/upload requests."""
    session_mgr = session_manager or SessionManager()

    filename = payload.get("filename")
    if not filename or not isinstance(filename, str):
        raise ValueError("Field 'filename' is required.")

    content_type = payload.get("contentType", "application/pdf")
    if content_type not in {"application/pdf", "image/png", "image/jpeg"}:
        raise ValueError(f"Unsupported content type: {content_type}. Use PDF, PNG, or JPEG.")

    document_type = payload.get("documentType", "SUPPORTING_REPORT")
    if document_type not in {"BILL", "DISCHARGE_SUMMARY", "SUPPORTING_REPORT"}:
        raise ValueError(f"Unsupported document type: {document_type}.")

    session_id = payload.get("session_id")
    claim_id = payload.get("claim_id")

    session = session_mgr.get_or_create_session(
        session_id=session_id,
        tenant_id=tenant_id,
        claim_id=claim_id,
    )

    doc_id = f"ai_doc_{uuid.uuid4().hex[:12]}"
    extracted_sample = f"Synthetic extraction for {filename} ({document_type})"

    doc_record = session_mgr.attach_uploaded_document(
        session_id=session.session_id,
        document_id=doc_id,
        filename=filename,
        document_type=document_type,
        extracted_text=extracted_sample,
    )

    return {
        "status": "READY",
        "documentId": doc_id,
        "session_id": session.session_id,
        "claim_id": session.claim_id,
        "document": doc_record,
        "message": f"Document '{filename}' successfully registered in AI review session.",
    }
