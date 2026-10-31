"""Unit tests for Score-Scale Integrity Across Retrieval Backends (AUB-RET-02 / T2.6).

Safety Properties (AUB Phase 2 / T2.6):
1. LexicalOverlapReranker never inflates scores beyond base score (removes 1.5x multiplier).
2. HybridRRFRetriever emits pure, authentic Reciprocal Rank Fusion scores without artificial
   rescaling to BM25 magnitude.
3. Confidence scores across backends (bm25, char_ngram, hybrid_rrf, hybrid_rrf_rerank)
   conform to documented [0.0, 1.0) calibration contracts.
4. Identical requests across backends evaluate fairly against calibrated thresholds.
"""

from __future__ import annotations

from triagerag.config import get_data_dir
from triagerag.contracts.enums import AbstainCode
from triagerag.rag.abstain import (
    evaluate_abstention_with_code,
    load_retrieval_config,
    normalize_relevance_score,
)
from triagerag.rag.hybrid import (
    CharNgramRetriever,
    HybridRRFRetriever,
    LexicalOverlapReranker,
)
from triagerag.rag.index import BM25ClinicalIndex
from triagerag.rag.ingest import ingest_protocols


def test_lexical_overlap_reranker_never_inflates_base_score() -> None:
    """T2.6 / AUB-RET-02: Reranker must never multiply score by 1.5x or exceed base score."""
    reranker = LexicalOverlapReranker()
    base_score = 4.0

    # Case 1: 100% token overlap (overlap_ratio = 1.0)
    query_tokens = {"ischemic", "chest", "discomfort"}
    doc_tokens_full = {"ischemic", "chest", "discomfort", "angina"}
    score_full = reranker.rerank(query_tokens, doc_tokens_full, base_score)

    # In the old code: base_score * (1 + 0.5 * 1.0) = 4.0 * 1.5 = 6.0 (inflated!)
    # In the hardened code: bounded by base_score (factor <= 1.0)
    assert score_full == base_score
    assert score_full <= base_score

    # Case 2: Partial overlap (overlap_ratio = 0.5)
    doc_tokens_half = {"ischemic", "other"}
    score_half = reranker.rerank(query_tokens, doc_tokens_half, base_score)
    assert score_half < base_score
    assert score_half > 0.0

    # Case 3: Zero overlap
    doc_tokens_zero = {"unrelated", "tokens"}
    score_zero = reranker.rerank(query_tokens, doc_tokens_zero, base_score)
    assert score_zero <= score_half
    assert score_zero > 0.0


def test_hybrid_rrf_emits_authentic_scores_without_bm25_rescale() -> None:
    """T2.6 / AUB-RET-02: Hybrid RRF scores must be pure fusion values, not rescaled to BM25."""
    data_dir = get_data_dir()
    chunks = ingest_protocols(data_dir)
    cfg = load_retrieval_config(data_dir)

    hybrid = HybridRRFRetriever(chunks, config=cfg)
    query = "chest pain ischemic discomfort"

    results = hybrid.search(query=query, population="adult", top_k=5, syndrome="chest_pain")
    assert len(results) > 0

    top_chunk, top_score = results[0]
    # Pure RRF score is sum of 1/(rrf_k + rank). With rrf_k=25, rank 1 in two retrievers:
    # max possible score = 2 * (1 / 26) = 0.0769
    # In the old code, this was artificially multiplied by max_bm25 (~2.5-3.5)
    # The hardened code emits authentic RRF scores:
    max_theoretical_rrf = 2.0 / (float(cfg.top_k * cfg.top_k) + 1.0)
    assert top_score <= max_theoretical_rrf + 0.001
    assert top_score > 0.0


def test_backend_confidence_normalization_contracts() -> None:
    """T2.6: normalize_relevance_score correctly normalizes each backend onto [0, 1]."""
    # 1. BM25 contract: s / (s + 1.0)
    bm25_conf = normalize_relevance_score(2.5, backend="bm25")
    assert 0.70 < bm25_conf < 0.75

    # 2. Hybrid RRF contract: s / max_theoretical_rrf
    rrf_raw = 2.0 / 26.0  # Rank 1 in both retrievers
    rrf_conf = normalize_relevance_score(rrf_raw, backend="hybrid_rrf", top_k=5)
    assert rrf_conf == 1.0

    # 3. Char-ngram contract: raw / 2.5
    ngram_conf = normalize_relevance_score(2.5, backend="char_ngram")
    assert ngram_conf == 1.0

    # All backends map non-positive to 0.0
    assert normalize_relevance_score(0.0, backend="bm25") == 0.0
    assert normalize_relevance_score(0.0, backend="hybrid_rrf") == 0.0
    assert normalize_relevance_score(0.0, backend="char_ngram") == 0.0


def test_same_request_evaluates_fairly_across_backends() -> None:
    """T2.6: Same clinical request across backends evaluates fairly against calibrated threshold."""
    data_dir = get_data_dir()
    chunks = ingest_protocols(data_dir)
    cfg = load_retrieval_config(data_dir)

    query = "chest pain ischemic discomfort angina"

    bm25_idx = BM25ClinicalIndex(chunks, config=cfg)
    ngram_idx = CharNgramRetriever(chunks, config=cfg)
    hybrid_idx = HybridRRFRetriever(chunks, config=cfg)
    rerank_idx = HybridRRFRetriever(chunks, rerank=True, config=cfg)

    for idx in (bm25_idx, ngram_idx, hybrid_idx, rerank_idx):
        results = idx.search(query=query, population="adult", top_k=5, syndrome="chest_pain")
        assert len(results) > 0

        abstained, code, reason = evaluate_abstention_with_code(
            scored_chunks=results,
            population="adult",
            population_available=True,
            threshold=cfg.calibrated_threshold,
            syndrome_provided=True,
            config=cfg,
            backend=idx.backend,
        )

        # None of the backends should abstain on this strong positive match
        assert (
            not abstained
        ), f"Backend '{idx.backend}' unexpectedly abstained: code={code}, reason={reason}"
        assert code == AbstainCode.NONE
