"""Document chunker for ClaimLens AI Agent.

Splits extracted documents and claim evidence into semantically meaningful chunks
while preserving complete source metadata.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import re
from typing import Any


@dataclass
class DocumentChunk:
    chunk_id: str
    document_id: str
    document_name: str
    document_type: str  # 'BILL' | 'DISCHARGE_SUMMARY' | 'SUPPORTING_REPORT' | 'CLAIM_FINDING'
    page_number: int
    claim_id: str
    text: str
    source_reference: str
    confidence: float = 100.0
    section: str | None = None
    extra_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "document_name": self.document_name,
            "document_type": self.document_type,
            "page_number": self.page_number,
            "claim_id": self.claim_id,
            "text": self.text,
            "source_reference": self.source_reference,
            "confidence": self.confidence,
            "section": self.section,
            "extra_metadata": self.extra_metadata,
        }


class DocumentChunker:
    """Chunks structured claim data and raw extracted texts into searchable semantic units."""

    def chunk_claim_data(self, claim_data: dict[str, Any] | None) -> list[DocumentChunk]:
        if not claim_data:
            return []

        chunks: list[DocumentChunk] = []
        claim_id = claim_data.get("claimId") or claim_data.get("id", "Unknown")

        # 1. Chunk from Findings & Cited Evidence
        for finding in claim_data.get("findings", []):
            fid = finding.get("id") or finding.get("checkId", "finding")
            title = finding.get("title", "")
            summary = finding.get("summary", "")
            status = finding.get("status", "FINDING")
            action = finding.get("reviewerAction", "OPEN")

            for ev in finding.get("evidence", []):
                doc_name = ev.get("documentName") or ev.get("document_id", "Document")
                doc_id = ev.get("documentId") or ev.get("document_id", "doc")
                page = ev.get("page", 1)
                conf = ev.get("confidence", 100.0)
                excerpt = (ev.get("excerpt") or "").strip()

                chunk_text = f"Finding: {title}. Status: {status}. Reviewer Action: {action}. Summary: {summary}. Evidence Excerpt: \"{excerpt}\""
                chunk_id = f"chk_{sha256(f'{claim_id}|{fid}|{doc_id}|{page}|{excerpt}'.encode()).hexdigest()[:16]}"
                source_ref = f"{doc_name} — Page {page}"

                chunks.append(
                    DocumentChunk(
                        chunk_id=chunk_id,
                        document_id=doc_id,
                        document_name=doc_name,
                        document_type=self._infer_doc_type(doc_name),
                        page_number=page,
                        claim_id=claim_id,
                        text=chunk_text,
                        source_reference=source_ref,
                        confidence=conf,
                        section="Findings & Evidence",
                        extra_metadata={"finding_id": fid, "finding_title": title},
                    )
                )

        # 2. Chunk from Document Records & Text Extractions
        for doc in claim_data.get("documents", []):
            doc_id = doc.get("id", "doc")
            doc_name = doc.get("name") or doc.get("filename", "Document")
            doc_type = doc.get("type") or doc.get("documentType", "SUPPORTING_REPORT")
            pages = doc.get("pages", 1)
            raw_text = doc.get("extractedText") or doc.get("text") or ""

            if raw_text.strip():
                # Split raw text by double newlines or sentences
                paragraphs = [p.strip() for p in re.split(r"\n\s*\n", raw_text) if p.strip()]
                for p_idx, para in enumerate(paragraphs):
                    chunk_id = f"chk_{sha256(f'{claim_id}|{doc_id}|{p_idx}|{para[:40]}'.encode()).hexdigest()[:16]}"
                    source_ref = f"{doc_name} — Page {min(p_idx + 1, pages)}"
                    chunks.append(
                        DocumentChunk(
                            chunk_id=chunk_id,
                            document_id=doc_id,
                            document_name=doc_name,
                            document_type=doc_type,
                            page_number=min(p_idx + 1, pages),
                            claim_id=claim_id,
                            text=para,
                            source_reference=source_ref,
                            confidence=doc.get("extractionQuality") or 95.0,
                            section="Document Body",
                        )
                    )

        return chunks

    def chunk_text(
        self,
        text: str,
        document_id: str,
        document_name: str,
        document_type: str,
        claim_id: str,
        page_number: int = 1,
        max_chunk_size: int = 400,
    ) -> list[DocumentChunk]:
        """Chunk an arbitrary document string into semantic text blocks."""
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        chunks: list[DocumentChunk] = []

        for p_idx, para in enumerate(paragraphs):
            # If paragraph is very large, split into sentence-based sub-chunks
            if len(para) > max_chunk_size:
                sentences = re.split(r"(?<=[.!?])\s+", para)
                current_chunk = []
                current_len = 0
                for sent in sentences:
                    if current_len + len(sent) > max_chunk_size and current_chunk:
                        chunk_content = " ".join(current_chunk)
                        chunk_id = f"chk_{sha256(f'{claim_id}|{document_id}|{len(chunks)}|{chunk_content[:30]}'.encode()).hexdigest()[:16]}"
                        chunks.append(
                            DocumentChunk(
                                chunk_id=chunk_id,
                                document_id=document_id,
                                document_name=document_name,
                                document_type=document_type,
                                page_number=page_number,
                                claim_id=claim_id,
                                text=chunk_content,
                                source_reference=f"{document_name} — Page {page_number}",
                            )
                        )
                        current_chunk = [sent]
                        current_len = len(sent)
                    else:
                        current_chunk.append(sent)
                        current_len += len(sent)
                if current_chunk:
                    chunk_content = " ".join(current_chunk)
                    chunk_id = f"chk_{sha256(f'{claim_id}|{document_id}|{len(chunks)}|{chunk_content[:30]}'.encode()).hexdigest()[:16]}"
                    chunks.append(
                        DocumentChunk(
                            chunk_id=chunk_id,
                            document_id=document_id,
                            document_name=document_name,
                            document_type=document_type,
                            page_number=page_number,
                            claim_id=claim_id,
                            text=chunk_content,
                            source_reference=f"{document_name} — Page {page_number}",
                        )
                    )
            else:
                chunk_id = f"chk_{sha256(f'{claim_id}|{document_id}|{p_idx}|{para[:30]}'.encode()).hexdigest()[:16]}"
                chunks.append(
                    DocumentChunk(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        document_name=document_name,
                        document_type=document_type,
                        page_number=page_number,
                        claim_id=claim_id,
                        text=para,
                        source_reference=f"{document_name} — Page {page_number}",
                    )
                )

        return chunks

    def _infer_doc_type(self, doc_name: str) -> str:
        name_lower = doc_name.lower()
        if "bill" in name_lower or "invoice" in name_lower:
            return "BILL"
        if "discharge" in name_lower or "summary" in name_lower:
            return "DISCHARGE_SUMMARY"
        return "SUPPORTING_REPORT"
