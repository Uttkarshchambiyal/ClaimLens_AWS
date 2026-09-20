"""Tool to inspect audit events and reviewer activity history."""
from __future__ import annotations

from typing import Any


class GetAuditHistoryTool:
    name = "get_audit_history"
    description = "Retrieve the immutable audit timeline and review activity log for the current claim."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    def execute(self, claim_data: dict[str, Any], **_kwargs) -> dict[str, Any]:
        if not claim_data:
            return {"error": "No claim data available in current session."}

        activity = claim_data.get("activity", [])
        return {
            "activity": [
                {
                    "id": a.get("id"),
                    "title": a.get("title"),
                    "detail": a.get("detail"),
                    "at": a.get("at"),
                    "actorId": a.get("actorId"),
                }
                for a in activity
            ],
            "totalActivityEvents": len(activity),
        }
