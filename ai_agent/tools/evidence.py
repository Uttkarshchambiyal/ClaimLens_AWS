"""Tool to inspect evidence citations, excerpts, page numbers, and confidence scores."""
from __future__ import annotations

from typing import Any


class GetEvidenceTool:
    name = "get_evidence"
    description = "Retrieve exact source evidence references, text excerpts, page numbers, confidence levels, and geometry for specific evidence IDs or across all findings."
    parameters = {
        "type": "object",
        "properties": {
            "evidence_id": {
                "type": "string",
                "description": "Optional specific evidence ID to retrieve",
            },
            "finding_id": {
                "type": "string",
                "description": "Optional finding ID to retrieve evidence for",
            },
        },
        "required": [],
    }

    def execute(
        self,
        claim_data: dict[str, Any],
        evidence_id: str | None = None,
        finding_id: str | None = None,
        **_kwargs,
    ) -> dict[str, Any]:
        if not claim_data:
            return {"error": "No claim data available in current session."}

        all_evidence: list[dict[str, Any]] = []
        for finding in claim_data.get("findings", []):
            if finding_id and finding.get("id") != finding_id and finding.get("checkId") != finding_id:
                continue
            for ev in finding.get("evidence", []):
                ref = {
                    "evidenceId": ev.get("evidenceId") or ev.get("evidence_id"),
                    "documentId": ev.get("documentId") or ev.get("document_id"),
                    "documentName": ev.get("documentName") or ev.get("document_id", "Unknown Document"),
                    "page": ev.get("page", 1),
                    "confidence": ev.get("confidence", 100.0),
                    "excerpt": ev.get("excerpt", ""),
                    "findingId": finding.get("id"),
                    "findingTitle": finding.get("title"),
                    "geometry": ev.get("geometry"),
                }
                if evidence_id:
                    if ref["evidenceId"] == evidence_id:
                        return {"evidence": [ref]}
                else:
                    all_evidence.append(ref)

        return {"evidence": all_evidence, "totalEvidenceItems": len(all_evidence)}
