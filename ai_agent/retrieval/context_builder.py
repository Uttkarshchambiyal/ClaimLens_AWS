"""Context builder that compiles and formats complete ClaimLens context safely."""
from __future__ import annotations

import os
from typing import Any


class ContextBuilder:
    def __init__(self, max_context_chars: int | None = None):
        self.max_context_chars = max_context_chars or int(os.getenv("AI_MAX_CONTEXT_SIZE", "8192"))

    def build_claim_context(self, claim_data: dict[str, Any] | None) -> str:
        if not claim_data:
            return "No claim context is currently loaded. (Guest/Empty Session)"

        lines = ["=== CLAIM CONTEXT ==="]
        claim_id = claim_data.get("claimId") or claim_data.get("id", "Unknown")
        status = claim_data.get("status", "UNKNOWN")
        lines.append(f"Claim ID: {claim_id}")
        lines.append(f"Analysis Status: {status}")
        lines.append(f"Analysis Version: {claim_data.get('analysisVersion', 1)}")
        lines.append(f"Review Priority: {claim_data.get('reviewPriority', 'MEDIUM')}")

        paise = claim_data.get("claimedAmountPaise")
        if paise is not None:
            lines.append(f"Claimed Invoice Total: ₹{paise / 100:,.2f} ({paise} paise)")
        else:
            lines.append("Claimed Invoice Total: Not provided")

        if claim_data.get("extractionQuality") is not None:
            lines.append(f"Extraction Quality: {claim_data.get('extractionQuality')}%")
        if claim_data.get("coverage") is not None:
            lines.append(f"Document Coverage: {claim_data.get('coverage')}%")

        # Documents
        docs = claim_data.get("documents", [])
        lines.append(f"\n--- DOCUMENTS ({len(docs)}) ---")
        for doc in docs:
            name = doc.get("name") or doc.get("filename", "Doc")
            dtype = doc.get("type") or doc.get("documentType", "UNKNOWN")
            pages = doc.get("pages", 1)
            quality = doc.get("extractionQuality")
            quality_str = f", Quality: {quality}%" if quality is not None else ""
            lines.append(f"- [{doc.get('id', 'doc')}] {name} ({dtype}, {pages} page(s){quality_str})")

        # Findings & Evidence
        findings = claim_data.get("findings", [])
        lines.append(f"\n--- FINDINGS & EVIDENCE ({len(findings)}) ---")
        for f in findings:
            fid = f.get("id", "fnd")
            title = f.get("title", "")
            fstatus = f.get("status", "FINDING")
            action = f.get("reviewerAction", "OPEN")
            summary = f.get("summary", "")
            lines.append(f"* Finding [{fid}] {title}")
            lines.append(f"  Status: {fstatus} | Reviewer Action: {action}")
            if summary:
                lines.append(f"  Summary: {summary}")

            ev_list = f.get("evidence", [])
            for ev in ev_list:
                doc_name = ev.get("documentName") or ev.get("document_id", "Doc")
                page = ev.get("page", 1)
                conf = ev.get("confidence", 100.0)
                excerpt = (ev.get("excerpt") or "").strip().replace("\n", " ")
                # Sanitize excerpt to prevent prompt injection breakouts
                safe_excerpt = excerpt.replace("```", "'''")
                lines.append(f"  - Evidence [Doc: {doc_name}, Page: {page}, Conf: {conf:.1f}%]: \"{safe_excerpt}\"")

            if f.get("requestedEvidence"):
                lines.append(f"  - Missing Evidence Needed: {f.get('requestedEvidence')}")

        # Reviewer Corrections
        corrections = claim_data.get("corrections", [])
        if corrections:
            lines.append(f"\n--- REVIEWER CORRECTIONS ({len(corrections)}) ---")
            for c in corrections:
                field_id = c.get("fieldId", "Field")
                val = c.get("correctedValue", "")
                actor = c.get("actorId", "Reviewer")
                lines.append(f"- Correction by {actor}: Field '{field_id}' -> '{val}' (Note: original preserved, checks not rerun)")

        # Audit Log
        activity = claim_data.get("activity", [])
        if activity:
            lines.append(f"\n--- AUDIT TIMELINE ({len(activity)}) ---")
            for act in activity[-5:]:  # show most recent 5
                title = act.get("title", "")
                detail = act.get("detail", "")
                at = act.get("at", "")
                lines.append(f"- [{at}] {title}: {detail}")

        full_text = "\n".join(lines)
        if len(full_text) > self.max_context_chars:
            full_text = full_text[: self.max_context_chars] + "\n... [Context truncated to fit budget]"

        return full_text
