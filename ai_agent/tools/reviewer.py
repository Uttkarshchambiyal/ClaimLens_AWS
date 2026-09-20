"""Tool to inspect reviewer dispositions and user corrections."""
from __future__ import annotations

from typing import Any


class GetReviewerDataTool:
    name = "get_reviewer_data"
    description = "Retrieve current human reviewer dispositions (OPEN, ACKNOWLEDGED, RESOLVED) and manual extraction corrections."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    def execute(self, claim_data: dict[str, Any], **_kwargs) -> dict[str, Any]:
        if not claim_data:
            return {"error": "No claim data available in current session."}

        actions = [
            {
                "findingId": f.get("id"),
                "findingTitle": f.get("title"),
                "reviewerAction": f.get("reviewerAction", "OPEN"),
            }
            for f in claim_data.get("findings", [])
        ]

        corrections = [
            {
                "correctionId": c.get("correctionId") or c.get("id"),
                "fieldId": c.get("fieldId"),
                "correctedValue": c.get("correctedValue"),
                "createdAt": c.get("createdAt"),
                "actorId": c.get("actorId"),
            }
            for c in claim_data.get("corrections", [])
        ]

        return {
            "reviewerDispositions": actions,
            "resolvedCount": sum(1 for a in actions if a["reviewerAction"] == "RESOLVED"),
            "acknowledgedCount": sum(1 for a in actions if a["reviewerAction"] == "ACKNOWLEDGED"),
            "openCount": sum(1 for a in actions if a["reviewerAction"] == "OPEN"),
            "corrections": corrections,
            "correctionsCount": len(corrections),
            "note": "Reviewer corrections are human annotations. Automated checks are not automatically rerun.",
        }
