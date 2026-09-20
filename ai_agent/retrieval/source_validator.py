"""Source validator that checks and verifies LLM-generated citations against real evidence."""
from __future__ import annotations

import re
from typing import Any


class SourceValidator:
    def validate_sources(
        self,
        candidate_sources: list[dict[str, Any]],
        claim_data: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """Validate candidate citations against ground-truth claim documents and evidence."""
        if not claim_data or not candidate_sources:
            return []

        # Build ground-truth document and evidence maps
        doc_names = set()
        doc_ids = set()
        for doc in claim_data.get("documents", []):
            if doc.get("name"):
                doc_names.add(doc["name"].lower())
            if doc.get("filename"):
                doc_names.add(doc["filename"].lower())
            if doc.get("id"):
                doc_ids.add(doc["id"].lower())

        valid_evidence_map: dict[str, dict[str, Any]] = {}
        for f in claim_data.get("findings", []):
            for ev in f.get("evidence", []):
                eid = ev.get("evidenceId") or ev.get("evidence_id")
                if eid:
                    valid_evidence_map[eid] = ev

        validated: list[dict[str, Any]] = []
        for src in candidate_sources:
            doc_name = src.get("documentName", "") or src.get("documentId", "")
            page = src.get("page")
            eid = src.get("evidenceId")

            # Check if evidenceId is genuine
            if eid and eid in valid_evidence_map:
                real_ev = valid_evidence_map[eid]
                validated.append({
                    "evidenceId": eid,
                    "documentName": real_ev.get("documentName") or real_ev.get("document_id", doc_name),
                    "page": real_ev.get("page", page or 1),
                    "confidence": real_ev.get("confidence", 100.0),
                    "excerpt": real_ev.get("excerpt", src.get("excerpt", "")),
                })
                continue

            # Check if documentName matches known documents
            if doc_name.lower() in doc_names or doc_name.lower() in doc_ids:
                validated.append({
                    "documentName": doc_name,
                    "page": page if isinstance(page, int) and page >= 1 else 1,
                    "confidence": src.get("confidence", 100.0),
                    "excerpt": src.get("excerpt", ""),
                })

        return validated

    def extract_and_validate_citations_from_text(
        self,
        text: str,
        claim_data: dict[str, Any] | None,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Parse in-text citations like [Doc: filename, Page: X] and sanitize against claim data."""
        if not claim_data:
            # Strip invalid citations from text when no claim exists
            cleaned = re.sub(r"\[(Doc|Document|Page|Evidence):?[^\]]+\]", "", text)
            return cleaned.strip(), []

        # Find patterns like [Doc: foo.pdf, Page: 2] or [CityCare_bill.pdf, Page 3]
        citation_pattern = re.compile(
            r"\[(?:Doc:\s*|Document:\s*)?([A-Za-z0-9_.\- ]+?),\s*(?:Page:\s*|p\.\s*|Page\s*)(\d+)(?:,\s*Conf:\s*([\d.]+)%?)?\]",
            re.IGNORECASE,
        )

        candidates = []
        for match in citation_pattern.finditer(text):
            doc_name, page_str, conf_str = match.groups()
            candidates.append({
                "documentName": doc_name.strip(),
                "page": int(page_str),
                "confidence": float(conf_str) if conf_str else 100.0,
            })

        valid_sources = self.validate_sources(candidates, claim_data)
        return text, valid_sources
