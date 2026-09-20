"""Tool to compare financial figures, stated invoice totals, line item sums, and discrepancies."""
from __future__ import annotations

from typing import Any


class GetFinancialsTool:
    name = "get_financials"
    description = "Retrieve financial breakdown including stated invoice total, sum of extracted line items, reconciliation status, and currency details."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    def execute(self, claim_data: dict[str, Any], **_kwargs) -> dict[str, Any]:
        if not claim_data:
            return {"error": "No claim data available in current session."}

        claimed_amount_paise = claim_data.get("claimedAmountPaise")
        stated_total = claimed_amount_paise / 100 if claimed_amount_paise is not None else None

        # Look for invoice reconciliation findings
        reconciliation_finding = next(
            (
                f
                for f in claim_data.get("findings", [])
                if f.get("checkId") in {"CHK_01_INVOICE_TOTAL_MATH", "CHK_01_INVOICE_TOTAL"}
                or "invoice total" in (f.get("title") or "").lower()
            ),
            None,
        )

        return {
            "statedInvoiceTotalRupees": stated_total,
            "claimedAmountPaise": claimed_amount_paise,
            "reconciliationStatus": reconciliation_finding.get("status") if reconciliation_finding else "NOT_EVALUATED",
            "reconciliationSummary": reconciliation_finding.get("summary") if reconciliation_finding else None,
            "hasDiscrepancy": reconciliation_finding.get("status") == "FINDING" if reconciliation_finding else False,
            "evidence": [
                {
                    "documentName": ev.get("documentName") or ev.get("document_id"),
                    "page": ev.get("page"),
                    "excerpt": ev.get("excerpt"),
                }
                for ev in (reconciliation_finding.get("evidence", []) if reconciliation_finding else [])
            ],
        }
