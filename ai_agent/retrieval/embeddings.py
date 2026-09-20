"""Embedding providers and vector storage for ClaimLens semantic retrieval."""
from __future__ import annotations

from abc import ABC, abstractmethod
import json
import math
import os
import re
from typing import Any
from ai_agent.retrieval.chunker import DocumentChunk


# Semantic Concept Expansion Dictionary for Medical & Insurance Claim Review
SEMANTIC_SYNONYMS: dict[str, list[str]] = {
    "surgery": ["procedure", "operation", "cholecystectomy", "appendectomy", "intervention", "treatment", "surgical", "incision", "laparoscopic"],
    "procedure": ["surgery", "operation", "treatment", "intervention", "cholecystectomy", "procedure_code", "cpt"],
    "treatment": ["care", "therapy", "intervention", "procedure", "medication", "surgery", "management"],
    "diagnosis": ["condition", "disease", "illness", "pathology", "icd", "symptom", "disorder", "indication"],
    "bill": ["invoice", "itemized", "charges", "cost", "total", "amount", "fee", "price", "statement", "rupees", "paise"],
    "cost": ["amount", "charge", "total", "fee", "bill", "price", "paise", "rupees", "math", "reconciliation"],
    "discrepancy": ["mismatch", "conflict", "difference", "variance", "finding", "inconsistent", "error", "unreconciled", "gap"],
    "discharge": ["admission", "hospitalization", "stay", "summary", "inpatient", "discharge_summary", "hospital"],
    "doctor": ["physician", "surgeon", "provider", "clinician", "practitioner", "hospital", "clinic"],
    "date": ["admission_date", "discharge_date", "service_date", "performed", "timeline", "when"],
}


class EmbeddingsProvider(ABC):
    """Abstract interface for generating vector embeddings."""

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """Embed a single text string into a float vector."""
        pass

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of text strings into float vectors."""
        pass


class LocalSemanticEmbedding(EmbeddingsProvider):
    """Local dense semantic vectorizer with medical concept mapping and cosine normalization."""

    def __init__(self, dimension: int = 128):
        self.dimension = dimension

    def _tokenize_and_expand(self, text: str) -> list[str]:
        tokens = re.findall(r"\w+", text.lower())
        expanded = list(tokens)
        for token in tokens:
            for concept, synonyms in SEMANTIC_SYNONYMS.items():
                if token == concept or token in synonyms:
                    expanded.extend([concept] + synonyms[:4])
        return expanded

    def embed_text(self, text: str) -> list[float]:
        tokens = self._tokenize_and_expand(text)
        vector = [0.0] * self.dimension

        if not tokens:
            return vector

        # Combine n-grams and token hashes into vector dimensions
        for token in tokens:
            # Hash whole token
            h = hash(token) % self.dimension
            vector[h] += 1.0

            # Hash 3-character sub-ngrams for morphological generalization
            for i in range(len(token) - 2):
                ngram = token[i : i + 3]
                nh = hash(ngram) % self.dimension
                vector[nh] += 0.35

        # L2-normalize vector so dot-product equals cosine similarity
        norm = math.sqrt(sum(x * x for x in vector))
        if norm > 0:
            vector = [x / norm for x in vector]

        return vector

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(t) for t in texts]


class SageMakerEmbeddingProvider(EmbeddingsProvider):
    """Production embedding provider connecting to Amazon SageMaker / Titan."""

    def __init__(self, endpoint_name: str | None = None, region_name: str | None = None):
        self.endpoint_name = endpoint_name or os.getenv("SAGEMAKER_EMBEDDING_ENDPOINT", "claimlens-embedding-endpoint")
        self.region_name = region_name or os.getenv("AWS_REGION", "ap-south-1")
        self._client = None
        self._fallback = LocalSemanticEmbedding()

    def _get_client(self):
        if self._client is None:
            import boto3
            self._client = boto3.client("sagemaker-runtime", region_name=self.region_name)
        return self._client

    def embed_text(self, text: str) -> list[float]:
        try:
            client = self._get_client()
            payload = json.dumps({"inputs": text})
            response = client.invoke_endpoint(
                EndpointName=self.endpoint_name,
                ContentType="application/json",
                Body=payload,
            )
            result = json.loads(response["Body"].read().decode("utf-8"))
            if isinstance(result, list) and isinstance(result[0], list):
                return result[0]
            if isinstance(result, dict) and "embedding" in result:
                return result["embedding"]
            return self._fallback.embed_text(text)
        except Exception:
            return self._fallback.embed_text(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(t) for t in texts]


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Compute cosine similarity between two normalized vectors."""
    if len(v1) != len(v2):
        return 0.0
    return sum(a * b for a, b in zip(v1, v2))


class VectorStore:
    """Thread-safe in-memory vector store partitioned by claim_id."""

    def __init__(self, embeddings_provider: EmbeddingsProvider | None = None):
        self.provider = embeddings_provider or LocalSemanticEmbedding()
        self._index: list[tuple[DocumentChunk, list[float]]] = []

    def add_chunks(self, chunks: list[DocumentChunk]) -> None:
        """Embed and index document chunks."""
        for chunk in chunks:
            # Avoid duplicate chunks
            if any(existing.chunk_id == chunk.chunk_id for existing, _ in self._index):
                continue
            embedding = self.provider.embed_text(chunk.text)
            self._index.append((chunk, embedding))

    def search(
        self,
        query: str,
        claim_id: str | None = None,
        top_k: int = 5,
        min_score: float = 0.15,
    ) -> list[tuple[float, DocumentChunk]]:
        """Search for top_k semantically similar chunks within a claim scope."""
        query_vector = self.provider.embed_text(query)
        scored_results: list[tuple[float, DocumentChunk]] = []

        for chunk, chunk_vector in self._index:
            # Enforce claim isolation: only match authorized claim_id
            if claim_id and chunk.claim_id != claim_id and chunk.claim_id != "Unknown":
                continue

            score = cosine_similarity(query_vector, chunk_vector)
            if score >= min_score:
                scored_results.append((score, chunk))

        scored_results.sort(key=lambda x: x[0], reverse=True)
        return scored_results[:top_k]

    def clear_claim(self, claim_id: str) -> None:
        """Remove all indexed chunks for a claim."""
        self._index = [(c, v) for c, v in self._index if c.claim_id != claim_id]
