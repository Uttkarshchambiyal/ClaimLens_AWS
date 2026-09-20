"""Tool to inspect deterministic and model findings."""
from __future__ import annotations

from typing import Any


class GetFindingsTool:
    name = "get_findings"
    description = "List and inspect discrepancy findings, check statuses (PASS, FINDING, INSUFFICIENT_EVIDENCE, ERROR), priorities, and requested evidence."
    parameters = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["ALL", "PASS", "FINDING", "INSUFFICIENT_EVIDENCE", "ERROR"],
                "description": "Optional status filter",
            },
        },
        "required": [],
    }

    def execute(self, claim_data: dict[str, Any], status: str = "ALL", **_kwargs) -> dict[str, Any]:
        if not claim_data:
            return {"error": "No claim data available in current session."}

        findings = claim_data.get("findings", [])
        if status != "ALL":
            findings = [f for f in findings if f.get("status") == status]

        return {
            "findings": [
                {
                    "id": f.get("id"),
                    "checkId": f.get("checkId") or f.get("check_id"),
                    "title": f.get("title", ""),
                    "summary": f.get("summary", ""),
                    "status": f.get("status", "FINDING"),
                    "priority": f.get("priority", "MEDIUM"),
                    "requestedEvidence": f.get("requestedEvidence") or f.get("requested_evidence"),
                    "reviewerAction": f.get("reviewerAction", "OPEN"),
                    "evidenceCount": len(f.get("evidence", [])),
                    "evidenceSummary": [
                        {
                            "documentName": e.get("documentName") or e.get("document_id"),
                            "page": e.get("page"),
                            "excerpt": e.get("excerpt"),
                        }
                        for e in f.get("evidence", [])
                    ],
                }
                for f in findings
            ],
            "totalFindings": len(findings),
        }
