"""Tool to inspect documents within a claim packet."""
from __future__ import annotations

from typing import Any


class GetDocumentsTool:
    name = "get_documents"
    description = "List all documents associated with the claim, including document names, types (BILL, DISCHARGE_SUMMARY, SUPPORTING_REPORT), versions, page counts, and extraction status."
    parameters = {
        "type": "object",
        "properties": {
            "document_type": {
                "type": "string",
                "enum": ["BILL", "DISCHARGE_SUMMARY", "SUPPORTING_REPORT", "ALL"],
                "description": "Optional filter by document type",
            },
        },
        "required": [],
    }

    def execute(self, claim_data: dict[str, Any], document_type: str = "ALL", **_kwargs) -> dict[str, Any]:
        if not claim_data:
            return {"error": "No claim data available in current session."}
        docs = claim_data.get("documents", [])
        if document_type != "ALL":
            docs = [d for d in docs if d.get("type") == document_type]
        return {
            "documents": [
                {
                    "id": d.get("id"),
                    "name": d.get("name") or d.get("filename", "Unnamed Document"),
                    "type": d.get("type") or d.get("documentType"),
                    "version": d.get("version", 1),
                    "pages": d.get("pages", 1),
                    "extractionQuality": d.get("extractionQuality"),
                    "status": d.get("status", "READY"),
                }
                for d in docs
            ],
            "totalDocuments": len(docs),
        }
