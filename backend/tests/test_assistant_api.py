import json

from claimlens.config import Settings
from claimlens.repository import InMemoryRepository


def test_assistant_chat_returns_only_tenant_scoped_evidence(monkeypatch):
    import claimlens.api as api

    repo = InMemoryRepository()
    repo.put_once("tenant-a", "DOCUMENT", "doc-1", {"filename": "bill.pdf", "documentType": "BILL", "version": 1})
    repo.put_once(
        "tenant-a",
        "ANALYSIS",
        "analysis-1",
        {
            "claimId": "CLM-100",
            "status": "COMPLETED_WITH_WARNINGS",
            "createdAt": "2026-09-20T00:00:00Z",
            "documentIds": ["doc-1"],
            "findings": [{"finding_id": "total", "check_id": "bill.total", "title": "Invoice total does not reconcile", "summary": "Line items are below the invoice total.", "status": "FINDING", "priority": "HIGH", "evidence_ids": ["ev-1"]}],
            "evidence": {"ev-1": {"evidence_id": "ev-1", "document_id": "doc-1", "document_version": 1, "page": 2, "block_ids": ["b-1"], "geometry": {"left": 0.1, "top": 0.1, "width": 0.2, "height": 0.1}, "confidence": 98.0, "excerpt": "Invoice total"}},
        },
    )
    settings = Settings()
    monkeypatch.setattr(api, "Settings", lambda: settings)
    monkeypatch.setattr(api, "_aws_dependencies", lambda _: (None, repo, None))
    event = {
        "rawPath": "/assistant/chat",
        "body": json.dumps({"message": "Explain the invoice total", "analysisId": "analysis-1"}),
        "requestContext": {"http": {"method": "POST"}, "authorizer": {"jwt": {"claims": {"token_use": "id", "custom:tenant_id": "tenant-a"}}}},
    }

    response = api.handler(event, None)
    body = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert "Invoice total does not reconcile" in body["answer"]
    assert body["sources"] == [{"documentName": "bill.pdf", "page": 2, "excerpt": "Invoice total"}]
