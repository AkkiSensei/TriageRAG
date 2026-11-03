"""Unit tests for Phase 7 MMR diversity re-ranking, nearest-miss diagnostics, and calibration refusal (AUB T7.6, HD-12)."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from eval.retrieval.calibrate import (
    CalibrationDataRefusalError,
    fit_isotonic_calibrator,
)
from triagerag.contracts.enums import Consciousness
from triagerag.contracts.schemas import (
    Age,
    Measured,
    Patient,
    Vitals,
)
from triagerag.rag.chunking import ProtocolChunk
from triagerag.rag.diagnostics import (
    apply_mmr_rerank,
    calculate_nearest_misses,
    compute_token_jaccard_similarity,
    explain_chunk_predicates,
)
from triagerag.rag.predicates import PredicateEvalResult
from triagerag.rag.retrieve import retrieve_protocol_chunks
from triagerag.rag.service import RetrievalService


def _make_dummy_chunk(
    chunk_id: str,
    text: str,
    requires: tuple[str, ...] = (),
    contra: tuple[str, ...] = (),
) -> ProtocolChunk:
    return ProtocolChunk(
        chunk_id=chunk_id,
        doc_id="PROTO-TEST",
        title="Protocol Test",
        section="1.0",
        population="adult",
        syndrome="asthma_severe",
        text=text,
        indexed_text=text,
        requires_predicates=requires,
        contraindicated_by=contra,
    )


def test_compute_token_jaccard_similarity():
    """Verify deterministic token Jaccard similarity."""
    assert compute_token_jaccard_similarity("salbutamol nebulized", "salbutamol nebulized") == 1.0
    assert (
        compute_token_jaccard_similarity("salbutamol nebulized", "epinephrine intramuscular") == 0.0
    )
    # Overlap: "salbutamol" in union of 3 words {"salbutamol", "nebulized", "iv"} -> 1/3
    assert compute_token_jaccard_similarity(
        "salbutamol nebulized", "salbutamol iv"
    ) == pytest.approx(1 / 3, rel=1e-2)
    assert compute_token_jaccard_similarity("", "salbutamol") == 0.0


def test_mmr_rerank_diversity():
    """Verify MMR favors diverse candidates over near-identical redundant candidates."""
    # Chunk A: Salbutamol nebulizer repeat 5mg
    chunk_a = _make_dummy_chunk("chk-a", "salbutamol nebulized 5mg repeat every 20 minutes")
    # Chunk B: Almost identical duplicate of A
    chunk_b = _make_dummy_chunk(
        "chk-b", "salbutamol nebulized 5mg repeat every 20 minutes continuous"
    )
    # Chunk C: High relevance alternative therapy (ipratropium bromide)
    chunk_c = _make_dummy_chunk("chk-c", "ipratropium bromide nebulized 500mcg add to second dose")

    # Raw scores: chunk_a=10.0, chunk_b=9.8, chunk_c=9.2
    candidates = [(chunk_a, 10.0), (chunk_b, 9.8), (chunk_c, 9.2)]

    # Standard top-2 ranking without MMR would choose [chunk_a, chunk_b]
    # MMR with lambda=0.6 penalizes chunk_b due to high Jaccard with chunk_a, selecting chunk_c
    selected = apply_mmr_rerank(candidates, top_k=2, lambda_param=0.5)

    assert len(selected) == 2
    assert selected[0][0].chunk_id == "chk-a"  # highest score always first
    assert selected[1][0].chunk_id == "chk-c"  # diverse chunk promoted over redundant chunk_b


def test_nearest_misses_and_rejection_reasons():
    """Verify nearest-misses diagnostics report rank and distance to threshold."""
    c1 = _make_dummy_chunk("c1", "text 1")
    c2 = _make_dummy_chunk("c2", "text 2")
    c3 = _make_dummy_chunk("c3", "text 3")

    candidates = [(c1, 5.0), (c2, 3.0), (c3, 1.5)]
    selected_ids = {"c1"}

    misses = calculate_nearest_misses(candidates, selected_ids, threshold=2.0)
    assert len(misses) == 2

    # c2 score is 3.0, above threshold 2.0 -> TOP_K_RANK_CUTOFF
    assert misses[0].chunk_id == "c2"
    assert misses[0].score == 3.0
    assert misses[0].delta_to_threshold == pytest.approx(1.0, rel=1e-2)
    assert misses[0].rejection_reason == "TOP_K_RANK_CUTOFF"

    # c3 score is 1.5, below threshold 2.0 -> BELOW_SCORE_THRESHOLD
    assert misses[1].chunk_id == "c3"
    assert misses[1].score == 1.5
    assert misses[1].delta_to_threshold == pytest.approx(-0.5, rel=1e-2)
    assert misses[1].rejection_reason == "BELOW_SCORE_THRESHOLD"


def test_explain_chunk_predicates():
    """Verify predicate explanation breaks down boosts, penalties, and neutral states."""
    chunk = _make_dummy_chunk(
        "c-pred",
        "text",
        requires=("pred_wheeze", "pred_hypoxia"),
        contra=("pred_allergy_salbutamol",),
    )
    evals = {
        "pred_wheeze": PredicateEvalResult.SATISFIED,
        "pred_hypoxia": PredicateEvalResult.NOT_SATISFIED,
        "pred_allergy_salbutamol": PredicateEvalResult.UNKNOWN,
    }

    details = explain_chunk_predicates(chunk, evals)
    assert len(details) == 3

    wheeze = next(d for d in details if d.predicate_id == "pred_wheeze")
    assert wheeze.clinical_effect == "BOOST"
    assert wheeze.status == PredicateEvalResult.SATISFIED.value

    hypoxia = next(d for d in details if d.predicate_id == "pred_hypoxia")
    assert hypoxia.clinical_effect == "PENALTY"
    assert hypoxia.status == PredicateEvalResult.NOT_SATISFIED.value

    allergy = next(d for d in details if d.predicate_id == "pred_allergy_salbutamol")
    assert allergy.clinical_effect == "NEUTRAL"
    assert allergy.status == PredicateEvalResult.UNKNOWN.value


def test_calibration_refusal_without_verified_clinician_annotations():
    """Verify HD-12: Isotonic and conformal calibration refuses without verified clinician labels."""
    with pytest.raises(CalibrationDataRefusalError, match="Calibration Refusal.*AUB HD-12"):
        fit_isotonic_calibrator(None)

    with pytest.raises(CalibrationDataRefusalError, match="Calibration Refusal.*AUB HD-12"):
        fit_isotonic_calibrator([])

    with pytest.raises(CalibrationDataRefusalError, match="Calibration Refusal.*AUB HD-12"):
        fit_isotonic_calibrator([{"label": 1, "score": 0.85}])  # unverified

    # Succeeds only with explicit verified clinician attribution
    fit_isotonic_calibrator([{"label": 1, "score": 0.85, "verified_clinician_id": "CLIN-DR-402"}])


def test_retrieval_report_includes_diagnostics():
    """Verify live retrieval service report includes populated diagnostics."""
    service = RetrievalService.create_default()
    patient = Patient(
        assessed_at=datetime(2026, 11, 1, 12, 0, tzinfo=UTC),
        age=Age(value=Decimal("45")),
        sex="female",
        pregnancy="no",
        weight_kg=Measured(value=Decimal("70.0"), source="measured"),
        vitals=Vitals(consciousness=Measured(value=Consciousness.A, source="measured")),
        allergy_history_status="confirmed_none",
        medication_history_status="confirmed_none",
        suspected_syndrome="anaphylaxis",
    )

    report = retrieve_protocol_chunks(
        index=service.index,
        patient=patient,
        top_k=3,
        context=service.context,
    )

    assert report.diagnostics is not None
    assert "nearest_misses" in report.diagnostics
    assert "mmr_applied" in report.diagnostics
    assert report.diagnostics["inferred_mode"] is False
