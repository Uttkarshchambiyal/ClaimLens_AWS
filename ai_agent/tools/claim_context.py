"""Tool to retrieve high-level claim metadata and status."""
from __future__ import annotations

from typing import Any


class GetClaimContextTool:
    name = "get_claim_context"
    description = "Retrieve claim overview metadata including claim ID, analysis status, priority, claimed amount, and coverage."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    def execute(self, claim_data: dict[str, Any], **_kwargs) -> dict[str, Any]:
        if not claim_data:
            return {"error": "No claim data available in current session."}
        return {
            "claimId": claim_data.get("claimId") or claim_data.get("id", "Unknown"),
            "analysisId": claim_data.get("id"),
            "status": claim_data.get("status", "UNKNOWN"),
            "analysisVersion": claim_data.get("analysisVersion", 1),
            "reviewPriority": claim_data.get("reviewPriority", "MEDIUM"),
            "claimedAmountPaise": claim_data.get("claimedAmountPaise"),
            "claimedAmountRupees": (claim_data.get("claimedAmountPaise") or 0) / 100 if claim_data.get("claimedAmountPaise") is not None else None,
            "extractionQuality": claim_data.get("extractionQuality"),
            "coverage": claim_data.get("coverage"),
            "createdAt": claim_data.get("createdAt"),
            "documentCount": len(claim_data.get("documents", [])),
            "findingsCount": len(claim_data.get("findings", [])),
        }
