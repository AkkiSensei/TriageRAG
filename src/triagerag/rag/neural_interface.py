"""Neural dense embedding and cross-encoder reranking interface architecture (T7.2 / AUB-RET-05 / HD-10).

Safety Properties (Rules R1, R2, R3, R12, Human Decision Gate HD-10):
1. Mandatory HD-10 gate: No unapproved neural model may be downloaded, loaded, or executed in production.
2. Abstract contracts define clean boundaries for local dense retrieval and cross-encoder reranking.
3. Fully offline: Zero network calls, local execution only, deterministic math.
4. Fail-closed: Missing weights or unapproved status raise NeuralModelApprovalError or return safe fallback.
5. Production default remains BM25.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from pydantic import BaseModel

from triagerag.rag.chunking import ProtocolChunk
from triagerag.rag.ingest import compute_corpus_hash

if TYPE_CHECKING:
    pass


class NeuralModelApprovalError(RuntimeError):
    """Raised when an unapproved neural model is invoked without HD-10 human authorization."""


class NeuralModelMetadata(BaseModel):
    """Metadata describing a local neural model, license, and provenance."""

    model_name: str
    model_version: str
    license: str
    dimensions: int = 384
    max_sequence_length: int = 512
    checksum_sha256: str | None = None
    is_approved: bool = False
    approval_status: str = "BLOCKED_EXTERNAL_HD10"
    notes: str = "Pending formal human decision gate HD-10 approval"


class NeuralInferenceConfig(BaseModel):
    """Deterministic configuration for local neural inference."""

    batch_size: int = 16
    device: str = "cpu"
    normalize_embeddings: bool = True
    deterministic_seed: int = 42
    top_k: int = 5


class EmbeddingModel(Protocol):
    """Protocol for local dense embedding models."""

    @property
    def metadata(self) -> NeuralModelMetadata: ...

    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


class CrossEncoderModel(Protocol):
    """Protocol for local cross-encoder reranking models."""

    @property
    def metadata(self) -> NeuralModelMetadata: ...

    def predict_pairs(self, pairs: list[tuple[str, str]]) -> list[float]: ...


class MockLocalEmbeddingModel:
    """Offline deterministic mock embedding model for testing neural interfaces without external weights (HD-10)."""

    def __init__(
        self,
        metadata: NeuralModelMetadata | None = None,
        config: NeuralInferenceConfig | None = None,
    ) -> None:
        self._metadata = metadata or NeuralModelMetadata(
            model_name="mock-local-embedder-v1",
            model_version="1.0.0-mock",
            license="Apache-2.0-Synthetic",
            dimensions=4,
            is_approved=True,  # Test mock only
            approval_status="TEST_MOCK_APPROVED",
        )
        self.config = config or NeuralInferenceConfig()

    @property
    def metadata(self) -> NeuralModelMetadata:
        return self._metadata

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Compute deterministic pseudo-embeddings from character hashing."""
        embeddings: list[list[float]] = []
        for text in texts:
            # 4 deterministic dimensions based on character counts
            v = [
                float(len(text) % 17) / 17.0,
                float(sum(ord(c) for c in text[:10]) % 23) / 23.0,
                float(sum(ord(c) for c in text[-10:] if text) % 29) / 29.0,
                1.0,
            ]
            norm = (sum(x * x for x in v)) ** 0.5 or 1.0
            embeddings.append([round(x / norm, 4) for x in v])
        return embeddings


class MockLocalCrossEncoderModel:
    """Offline deterministic mock cross-encoder model for testing reranking interfaces (HD-10)."""

    def __init__(
        self,
        metadata: NeuralModelMetadata | None = None,
    ) -> None:
        self._metadata = metadata or NeuralModelMetadata(
            model_name="mock-local-cross-encoder-v1",
            model_version="1.0.0-mock",
            license="Apache-2.0-Synthetic",
            is_approved=True,
            approval_status="TEST_MOCK_APPROVED",
        )

    @property
    def metadata(self) -> NeuralModelMetadata:
        return self._metadata

    def predict_pairs(self, pairs: list[tuple[str, str]]) -> list[float]:
        """Compute deterministic query-passage relevance scores."""
        scores: list[float] = []
        for query, passage in pairs:
            q_words = set(query.lower().split())
            p_words = set(passage.lower().split())
            overlap = len(q_words & p_words)
            score = round(min(1.0, float(overlap) / max(1, len(q_words))), 4)
            scores.append(score)
        return scores


class NeuralDenseRetriever:
    """Dense vector retriever implementing the Retriever protocol (T7.2).

    Adheres strictly to HD-10: Refuses execution if model is unapproved.
    """

    def __init__(
        self,
        chunks: list[ProtocolChunk],
        embedder: EmbeddingModel,
        config: NeuralInferenceConfig | None = None,
        retrieval_context: Any | None = None,
    ) -> None:
        self.backend: str = "neural_dense"
        self.index_version: str = "1.0.0"
        self.corpus_hash: str = compute_corpus_hash(chunks)
        self.embedder: EmbeddingModel = embedder
        self.config: NeuralInferenceConfig = config or NeuralInferenceConfig()
        self.retrieval_context: Any | None = retrieval_context

        # Verify HD-10 gate before indexing
        if not self.embedder.metadata.is_approved:
            raise NeuralModelApprovalError(
                f"HD-10 GATE ENFORCED: Model '{self.embedder.metadata.model_name}' is not approved "
                f"for clinical or research retrieval (status: {self.embedder.metadata.approval_status})."
            )

        self.index_by_population: dict[str, list[ProtocolChunk]] = {}
        self.chunk_embeddings: dict[str, list[float]] = {}

        for ch in chunks:
            pop = ch.population.lower().strip()
            self.index_by_population.setdefault(pop, []).append(ch)

        # Pre-compute chunk embeddings
        if chunks:
            texts = [f"{ch.doc_id} {ch.section} {ch.text}" for ch in chunks]
            vecs = self.embedder.embed_texts(texts)
            for ch, vec in zip(chunks, vecs, strict=True):
                self.chunk_embeddings[ch.chunk_id] = vec

    def known_syndromes(self, population: str | None = None) -> set[str]:
        if population is None:
            return {
                ch.syndrome
                for chunks in self.index_by_population.values()
                for ch in chunks
                if ch.syndrome
            }
        pop = population.lower().strip()
        return {ch.syndrome for ch in self.index_by_population.get(pop, []) if ch.syndrome}

    def search(
        self,
        query: str,
        population: str,
        top_k: int | None = None,
        syndrome: str | None = None,
    ) -> list[tuple[ProtocolChunk, float]]:
        """Execute cosine similarity vector search over population and syndrome filtered chunks."""
        eff_k = top_k if top_k is not None else self.config.top_k
        pop = population.lower().strip()
        candidates = self.index_by_population.get(pop, [])
        if syndrome:
            candidates = [c for c in candidates if c.syndrome == syndrome]

        if not candidates or not query.strip():
            return []

        q_vec = self.embedder.embed_texts([query])[0]
        scored: list[tuple[ProtocolChunk, float]] = []

        for ch in candidates:
            ch_vec = self.chunk_embeddings.get(ch.chunk_id)
            if not ch_vec or len(ch_vec) != len(q_vec):
                continue
            # Cosine similarity (vectors are normalized)
            sim = sum(a * b for a, b in zip(q_vec, ch_vec, strict=True))
            sim_clamped = max(0.0, min(1.0, float(sim)))
            scored.append((ch, round(sim_clamped, 4)))

        scored.sort(key=lambda x: (x[1], x[0].chunk_id), reverse=True)
        return scored[:eff_k]

    def expand_parents(self, chunks: list[ProtocolChunk]) -> list[ProtocolChunk]:
        """Parent node expansion for hierarchical chunks."""
        return list(chunks)


class NeuralCrossEncoderReranker:
    """Cross-encoder reranker for reranking candidate chunks (T7.2).

    Adheres strictly to HD-10: Refuses execution if cross-encoder model is unapproved.
    """

    def __init__(
        self,
        cross_encoder: CrossEncoderModel,
        config: NeuralInferenceConfig | None = None,
    ) -> None:
        self.cross_encoder = cross_encoder
        self.config = config or NeuralInferenceConfig()

        if not self.cross_encoder.metadata.is_approved:
            raise NeuralModelApprovalError(
                f"HD-10 GATE ENFORCED: Cross-encoder '{self.cross_encoder.metadata.model_name}' "
                f"is not approved (status: {self.cross_encoder.metadata.approval_status})."
            )

    def rerank(
        self,
        query: str,
        scored_chunks: list[tuple[ProtocolChunk, float]],
        top_k: int = 5,
    ) -> list[tuple[ProtocolChunk, float]]:
        """Rerank initial candidate chunks using the cross-encoder score."""
        if not scored_chunks or not query.strip():
            return []

        pairs = [(query, ch.text) for ch, _ in scored_chunks]
        new_scores = self.cross_encoder.predict_pairs(pairs)

        rescored: list[tuple[ProtocolChunk, float]] = []
        for (ch, _orig_score), score in zip(scored_chunks, new_scores, strict=True):
            rescored.append((ch, score))

        rescored.sort(key=lambda x: (x[1], x[0].chunk_id), reverse=True)
        return rescored[:top_k]
