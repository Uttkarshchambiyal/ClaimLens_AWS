"""Evidence retriever that matches query intents to concrete evidence records."""
from __future__ import annotations

import re
from typing import Any


class EvidenceRetriever:
    def retrieve_relevant_evidence(
        self, query: str, claim_data: dict[str, Any] | None, max_results: int = 5
    ) -> list[dict[str, Any]]:
        if not claim_data:
            return []

        query_terms = set(re.findall(r"\w+", query.lower()))
        matched_items: list[tuple[float, dict[str, Any]]] = []

        findings = claim_data.get("findings", [])
        for f in findings:
            f_text = f"{f.get('title', '')} {f.get('summary', '')} {f.get('checkId', '')}".lower()
            f_terms = set(re.findall(r"\w+", f_text))
            f_score = len(query_terms.intersection(f_terms))

            for ev in f.get("evidence", []):
                ev_text = f"{ev.get('documentName', '')} {ev.get('excerpt', '')}".lower()
                ev_terms = set(re.findall(r"\w+", ev_text))
                ev_score = f_score + len(query_terms.intersection(ev_terms)) * 2

                item = {
                    "evidenceId": ev.get("evidenceId") or ev.get("evidence_id"),
                    "documentId": ev.get("documentId") or ev.get("document_id"),
                    "documentName": ev.get("documentName") or ev.get("document_id", "Document"),
                    "page": ev.get("page", 1),
                    "confidence": ev.get("confidence", 100.0),
                    "excerpt": ev.get("excerpt", ""),
                    "findingId": f.get("id"),
                    "findingTitle": f.get("title"),
                    "geometry": ev.get("geometry"),
                }
                matched_items.append((ev_score, item))

        # Sort by relevance score descending
        matched_items.sort(key=lambda x: x[0], reverse=True)

        results: list[dict[str, Any]] = []
        seen_ids = set()
        for score, item in matched_items:
            eid = item.get("evidenceId")
            if eid and eid in seen_ids:
                continue
            if eid:
                seen_ids.add(eid)
            results.append(item)
            if len(results) >= max_results:
                break

        return results
