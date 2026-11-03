"""Unit tests for Neural dense retriever and cross-encoder architecture (T7.2 / HD-10).

Safety Properties (Rules R1, R2, R3, R12, Human Decision Gate HD-10):
1. HD-10 refusal: An unapproved model metadata raises NeuralModelApprovalError.
2. Fully conforming: NeuralDenseRetriever satisfies the Retriever protocol.
3. Hard filters: Population and syndrome filters are strictly applied.
4. Reranker: NeuralCrossEncoderReranker preserves deterministic reranking.
5. Production default: BM25 remains production default.
"""

from __future__ import annotations

import pytest

from triagerag.rag.chunking import ProtocolChunk
from triagerag.rag.index import Retriever
from triagerag.rag.neural_interface import (
    MockLocalCrossEncoderModel,
    MockLocalEmbeddingModel,
    NeuralCrossEncoderReranker,
    NeuralDenseRetriever,
    NeuralModelApprovalError,
    NeuralModelMetadata,
)


def _build_test_chunks() -> list[ProtocolChunk]:
    return [
        ProtocolChunk(
            doc_id="adult_asthma",
            title="Adult Asthma",
            section="initial_management",
            chunk_id="chunk_adult_asthma_01",
            text="Administer supplemental oxygen and nebulized salbutamol.",
            population="adult",
            syndrome="asthma",
            license="Open Government Licence v3.0",
        ),
        ProtocolChunk(
            doc_id="adult_anaphylaxis",
            title="Adult Anaphylaxis",
            section="immediate_resuscitation",
            chunk_id="chunk_adult_ana_01",
            text="Administer intramuscular epinephrine 0.5 mg immediately.",
            population="adult",
            syndrome="anaphylaxis",
            license="Open Government Licence v3.0",
        ),
        ProtocolChunk(
            doc_id="paed_anaphylaxis",
            title="Paediatric Anaphylaxis",
            section="immediate_resuscitation",
            chunk_id="chunk_paed_ana_01",
            text="Administer intramuscular epinephrine 0.15 mg immediately for paediatric shock.",
            population="paediatric",
            syndrome="anaphylaxis",
            license="Open Government Licence v3.0",
        ),
    ]


def test_hd10_unapproved_model_raises_approval_error() -> None:
    """T7.2 / HD-10: An unapproved model cannot be loaded into NeuralDenseRetriever."""
    unapproved_meta = NeuralModelMetadata(
        model_name="unapproved-clinical-transformer",
        model_version="0.1.0-unauthorized",
        license="UNKNOWN_PROPRIETARY",
        is_approved=False,
        approval_status="BLOCKED_EXTERNAL_HD10",
    )
    embedder = MockLocalEmbeddingModel(metadata=unapproved_meta)
    chunks = _build_test_chunks()

    with pytest.raises(NeuralModelApprovalError) as exc_info:
        NeuralDenseRetriever(chunks=chunks, embedder=embedder)

    assert "HD-10 GATE ENFORCED" in str(exc_info.value)
    assert "is not approved" in str(exc_info.value)


def test_hd10_unapproved_cross_encoder_raises_approval_error() -> None:
    """T7.2 / HD-10: An unapproved cross-encoder cannot be loaded into NeuralCrossEncoderReranker."""
    unapproved_meta = NeuralModelMetadata(
        model_name="unapproved-cross-encoder",
        model_version="0.1.0-unauthorized",
        license="UNKNOWN_PROPRIETARY",
        is_approved=False,
        approval_status="BLOCKED_EXTERNAL_HD10",
    )
    cross_enc = MockLocalCrossEncoderModel(metadata=unapproved_meta)

    with pytest.raises(NeuralModelApprovalError) as exc_info:
        NeuralCrossEncoderReranker(cross_encoder=cross_enc)

    assert "HD-10 GATE ENFORCED" in str(exc_info.value)


def test_approved_mock_retriever_conforms_to_protocol() -> None:
    """T7.2: Approved mock embedder creates a valid Retriever conforming to protocol."""
    embedder = MockLocalEmbeddingModel()  # is_approved=True in mock
    chunks = _build_test_chunks()
    retriever = NeuralDenseRetriever(chunks=chunks, embedder=embedder)

    assert isinstance(retriever, Retriever)
    assert retriever.backend == "neural_dense"
    assert retriever.index_version == "1.0.0"
    assert "adult" in retriever.index_by_population
    assert "paediatric" in retriever.index_by_population

    known = retriever.known_syndromes()
    assert "asthma" in known
    assert "anaphylaxis" in known

    # Hard population filter
    results_adult = retriever.search("epinephrine", population="adult", top_k=5)
    assert len(results_adult) > 0
    assert all(c.population == "adult" for c, _ in results_adult)

    # Hard syndrome filter
    results_asthma = retriever.search("epinephrine", population="adult", syndrome="asthma")
    assert len(results_asthma) > 0
    assert all(c.syndrome == "asthma" for c, _ in results_asthma)


def test_approved_mock_cross_encoder_reranks_deterministically() -> None:
    """T7.2: Approved cross-encoder reranker scores query-passage pairs."""
    cross_enc = MockLocalCrossEncoderModel()
    reranker = NeuralCrossEncoderReranker(cross_encoder=cross_enc)

    chunks = _build_test_chunks()
    initial_scored = [(chunks[0], 0.5), (chunks[1], 0.4)]
    query = "epinephrine administration"

    reranked = reranker.rerank(query=query, scored_chunks=initial_scored, top_k=2)
    assert len(reranked) == 2
    # chunk 1 text contains 'epinephrine' and 'administer', so should rank higher than chunk 0
    assert reranked[0][0].chunk_id == "chunk_adult_ana_01"
