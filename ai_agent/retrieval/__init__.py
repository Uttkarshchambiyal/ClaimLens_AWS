"""ClaimLens AI Retrieval and Context Package."""
from .chunker import DocumentChunk, DocumentChunker
from .context_builder import ContextBuilder
from .embeddings import (
    EmbeddingsProvider,
    LocalSemanticEmbedding,
    SageMakerEmbeddingProvider,
    VectorStore,
    cosine_similarity,
)
from .evidence_retriever import EvidenceRetriever
from .hybrid_retriever import HybridRetriever
from .semantic_retriever import SemanticRetriever
from .source_validator import SourceValidator

__all__ = [
    "ContextBuilder",
    "DocumentChunk",
    "DocumentChunker",
    "EmbeddingsProvider",
    "EvidenceRetriever",
    "HybridRetriever",
    "LocalSemanticEmbedding",
    "SageMakerEmbeddingProvider",
    "SemanticRetriever",
    "SourceValidator",
    "VectorStore",
    "cosine_similarity",
]

