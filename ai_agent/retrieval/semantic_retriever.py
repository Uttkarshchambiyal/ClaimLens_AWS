"""Semantic retriever that indexes and retrieves document chunks based on vector embedding similarity."""
from __future__ import annotations

from typing import Any
from ai_agent.retrieval.chunker import DocumentChunk, DocumentChunker
from ai_agent.retrieval.embeddings import EmbeddingsProvider, LocalSemanticEmbedding, VectorStore


class SemanticRetriever:
    """Manages document chunk indexing and semantic vector retrieval."""

    def __init__(
        self,
        embeddings_provider: EmbeddingsProvider | None = None,
        chunker: DocumentChunker | None = None,
        vector_store: VectorStore | None = None,
    ):
        self.provider = embeddings_provider or LocalSemanticEmbedding()
        self.chunker = chunker or DocumentChunker()
        self.vector_store = vector_store or VectorStore(self.provider)

    def index_claim(self, claim_data: dict[str, Any] | None) -> list[DocumentChunk]:
        """Chunk and index all documents and evidence in the given claim context."""
        if not claim_data:
            return []
        chunks = self.chunker.chunk_claim_data(claim_data)
        self.vector_store.add_chunks(chunks)
        return chunks

    def retrieve(
        self,
        query: str,
        claim_data: dict[str, Any] | None = None,
        top_k: int = 5,
        min_score: float = 0.15,
    ) -> list[tuple[float, DocumentChunk]]:
        """Retrieve semantically relevant chunks for a user query."""
        if claim_data:
            self.index_claim(claim_data)

        claim_id = (claim_data.get("claimId") or claim_data.get("id")) if claim_data else None
        return self.vector_store.search(
            query=query,
            claim_id=claim_id,
            top_k=top_k,
            min_score=min_score,
        )
