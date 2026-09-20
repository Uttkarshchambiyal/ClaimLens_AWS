"""Hybrid retriever combining semantic embeddings, exact lexical matching, and structured claim data."""
from __future__ import annotations

import re
from typing import Any
from ai_agent.retrieval.chunker import DocumentChunk
from ai_agent.retrieval.semantic_retriever import SemanticRetriever


class HybridRetriever:
    """Fuses semantic vector retrieval, exact keyword/code retrieval, and structured claim retrieval."""

    def __init__(self, semantic_retriever: SemanticRetriever | None = None):
        self.semantic_retriever = semantic_retriever or SemanticRetriever()

    def retrieve(
        self,
        query: str,
        claim_data: dict[str, Any] | None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        if not claim_data:
            return []

        # 1. Semantic Retrieval
        semantic_results = self.semantic_retriever.retrieve(query, claim_data, top_k=top_k * 2)

        # 2. Exact Lexical Match
        exact_results = self._exact_match_search(query, claim_data)

        # 3. Check for Multi-Document Comparison Intent
        is_comparison = self._is_comparison_query(query)

        # 4. Result Fusion (Reciprocal Rank Fusion)
        fused_scores: dict[str, tuple[float, DocumentChunk]] = {}

        # Add semantic scores (RRF)
        for rank, (score, chunk) in enumerate(semantic_results):
            rrf_score = (1.0 / (60 + rank)) * 0.6 + (score * 0.4)
            fused_scores[chunk.chunk_id] = (rrf_score, chunk)

        # Add exact matching scores
        for rank, (score, chunk) in enumerate(exact_results):
            exact_rrf = (1.0 / (60 + rank)) * 0.5 + (score * 0.5)
            if chunk.chunk_id in fused_scores:
                prev_score, _ = fused_scores[chunk.chunk_id]
                fused_scores[chunk.chunk_id] = (prev_score + exact_rrf, chunk)
            else:
                fused_scores[chunk.chunk_id] = (exact_rrf, chunk)

        # Sort combined results
        sorted_chunks = sorted(fused_scores.values(), key=lambda x: x[0], reverse=True)

        # If it's a comparison query, ensure diverse representation across document types
        if is_comparison:
            selected = self._ensure_document_diversity([c for _, c in sorted_chunks], claim_data, max_items=top_k)
        else:
            selected = [c for _, c in sorted_chunks[:top_k]]

        # Format output into evidence references
        final_evidence: list[dict[str, Any]] = []
        for chunk in selected:
            final_evidence.append({
                "chunkId": chunk.chunk_id,
                "documentId": chunk.document_id,
                "documentName": chunk.document_name,
                "documentType": chunk.document_type,
                "page": chunk.page_number,
                "confidence": chunk.confidence,
                "excerpt": chunk.text,
                "sourceReference": chunk.source_reference,
            })

        return final_evidence

    def _exact_match_search(self, query: str, claim_data: dict[str, Any]) -> list[tuple[float, DocumentChunk]]:
        """Identify exact mentions of amounts, codes, claim IDs, or dates."""
        exact_tokens = set(re.findall(r"(?:₹|\b)\d+(?:,\d+)*(?:\.\d+)?\b|\bCLM-\d+\b|\bCHK_\w+\b|\b[A-Z0-9_-]{4,}\b", query, re.IGNORECASE))
        if not exact_tokens:
            return []

        matched_chunks: list[tuple[float, DocumentChunk]] = []
        all_chunks = self.semantic_retriever.chunker.chunk_claim_data(claim_data)

        for chunk in all_chunks:
            chunk_lower = chunk.text.lower()
            matches = sum(1 for token in exact_tokens if token.lower() in chunk_lower)
            if matches > 0:
                score = matches / len(exact_tokens)
                matched_chunks.append((score, chunk))

        matched_chunks.sort(key=lambda x: x[0], reverse=True)
        return matched_chunks

    def _is_comparison_query(self, query: str) -> bool:
        q_lower = query.lower()
        comparison_keywords = [
            "compare", "discrepanc", "conflict", "agree", "match", "inconsistent",
            "difference", "versus", "vs", "support the procedure", "both documents",
            "across documents", "across files"
        ]
        return any(kw in q_lower for kw in comparison_keywords)

    def _ensure_document_diversity(
        self,
        chunks: list[DocumentChunk],
        claim_data: dict[str, Any],
        max_items: int = 5,
    ) -> list[DocumentChunk]:
        """Ensure evidence contains chunks from multiple document types for comparison."""
        selected: list[DocumentChunk] = []
        doc_types_seen = set()

        # First pass: collect highest scoring chunk per document type
        for chunk in chunks:
            if chunk.document_type not in doc_types_seen:
                selected.append(chunk)
                doc_types_seen.add(chunk.document_type)
            if len(selected) >= max_items:
                break

        # Second pass: fill remaining slots with next best chunks
        for chunk in chunks:
            if chunk not in selected:
                selected.append(chunk)
            if len(selected) >= max_items:
                break

        return selected
