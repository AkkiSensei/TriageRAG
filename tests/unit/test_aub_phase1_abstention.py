"""Unit tests for AUB Phase 1 Task T1.4: Abstain Code Accuracy (AUB-ABS-01).

Safety Property (T1.4 / AUB-ABS-01):
1. Distinguish NO_POPULATION_COVERAGE (population unsupported in corpus) from
   NO_RESULTS (population supported, but retrieval query produced 0 chunks).
2. Distinguish both from LOW_CONFIDENCE (results found, but score below threshold).
3. Backwards-compatible evaluate_abstention preserves (abstained, reason) contract.
4. Engine verdict resolution fails closed to UNVERIFIED on NO_RESULTS.
"""

from __future__ import annotations

from triagerag.contracts.enums import AbstainCode, Verdict
from triagerag.contracts.schemas import RetrievalReport
from triagerag.engine.verdict import resolve_verdict_with_reason
from triagerag.rag.abstain import (
    evaluate_abstention,
    evaluate_abstention_with_code,
)
from triagerag.rag.chunking import ProtocolChunk


def _make_dummy_chunk(chunk_id: str, syndrome: str = "anaphylaxis") -> ProtocolChunk:
    return ProtocolChunk(
        chunk_id=chunk_id,
        doc_id="DOC_SYNTH_01",
        section="Section 1",
        population="adult",
        syndrome=syndrome,
        title="Emergency Protocol",
        text="Administer epinephrine 0.5 mg IM.",
    )


def test_abstain_no_population_coverage() -> None:
    """When population is unavailable in corpus, return NO_POPULATION_COVERAGE."""
    abstained, code, reason = evaluate_abstention_with_code(
        scored_chunks=[],
        population="neonatal",
        population_available=False,
    )
    assert abstained is True
    assert code == AbstainCode.NO_POPULATION_COVERAGE
    assert reason is not None
    assert "No verified protocol chunks available for population 'neonatal'" in reason


def test_abstain_no_results_when_population_is_available() -> None:
    """When population exists but retrieval produces 0 chunks, return NO_RESULTS (AUB-ABS-01)."""
    abstained, code, reason = evaluate_abstention_with_code(
        scored_chunks=[],
        population="adult",
        population_available=True,
    )
    assert abstained is True
    assert code == AbstainCode.NO_RESULTS
    assert reason is not None
    assert "No protocol chunks matched retrieval query for population 'adult'" in reason


def test_abstain_low_confidence() -> None:
    """When results exist but top score is below calibrated threshold, return LOW_CONFIDENCE."""
    chunk = _make_dummy_chunk("CHUNK_01")
    # Raw BM25 score of 0.05 normalizes to below default threshold 0.15
    abstained, code, reason = evaluate_abstention_with_code(
        scored_chunks=[(chunk, 0.05)],
        population="adult",
        population_available=True,
        threshold=0.5,
    )
    assert abstained is True
    assert code == AbstainCode.LOW_CONFIDENCE
    assert reason is not None
    assert "below calibrated threshold" in reason


def test_abstain_ambiguous_margin() -> None:
    """When top two syndromes are too close without explicit syndrome, return AMBIGUOUS_MARGIN."""
    c1 = _make_dummy_chunk("C1", syndrome="asthma")
    c2 = _make_dummy_chunk("C2", syndrome="copd")
    abstained, code, reason = evaluate_abstention_with_code(
        scored_chunks=[(c1, 10.0), (c2, 9.8)],
        population="adult",
        population_available=True,
        syndrome_provided=False,
        min_margin=0.20,
    )
    assert abstained is True
    assert code == AbstainCode.AMBIGUOUS_MARGIN
    assert reason is not None
    assert "Ambiguous syndrome match" in reason


def test_abstain_syndrome_inferred_when_margin_clear() -> None:
    """When syndrome inferred from flags with clear margin, return SYNDROME_INFERRED."""
    c1 = _make_dummy_chunk("C1", syndrome="asthma")
    c2 = _make_dummy_chunk("C2", syndrome="copd")
    abstained, code, reason = evaluate_abstention_with_code(
        scored_chunks=[(c1, 15.0), (c2, 5.0)],
        population="adult",
        population_available=True,
        syndrome_provided=False,
        min_margin=0.20,
    )
    assert abstained is False
    assert code == AbstainCode.SYNDROME_INFERRED
    assert reason is not None
    assert "Syndrome 'asthma' inferred from physiological flags" in reason


def test_no_abstain_when_syndrome_provided_and_score_high() -> None:
    """When suspected syndrome is provided and relevance is high, return NONE."""
    chunk = _make_dummy_chunk("CHUNK_01", syndrome="anaphylaxis")
    abstained, code, reason = evaluate_abstention_with_code(
        scored_chunks=[(chunk, 15.0)],
        population="adult",
        population_available=True,
        syndrome_provided=True,
    )
    assert abstained is False
    assert code == AbstainCode.NONE
    assert reason is None


def test_backwards_compatible_evaluate_abstention() -> None:
    """evaluate_abstention returns (bool, str | None) tuple matching underlying code."""
    # 1. NO_RESULTS case
    abstained, reason = evaluate_abstention(
        scored_chunks=[],
        population="adult",
        population_available=True,
    )
    assert abstained is True
    assert reason is not None
    assert "No protocol chunks matched retrieval query" in reason

    # 2. NO_POPULATION_COVERAGE case
    abstained_pop, reason_pop = evaluate_abstention(
        scored_chunks=[],
        population="unknown_pop",
        population_available=False,
    )
    assert abstained_pop is True
    assert "No verified protocol chunks available for population" in (reason_pop or "")


def test_verdict_fails_closed_on_no_results() -> None:
    """Engine verdict resolution must fail closed to UNVERIFIED on AbstainCode.NO_RESULTS."""
    retrieval_report = RetrievalReport(
        chunks=[],
        backend="bm25",
        abstained=True,
        abstain_code=AbstainCode.NO_RESULTS,
        reason="No protocol chunks matched retrieval query for population 'adult'",
        query="hypotension tachycardia",
    )

    verdict, unverified_reason = resolve_verdict_with_reason(
        has_block=False,
        has_skip_or_unresolved=False,
        has_alert=False,
        retrieval_report=retrieval_report,
        has_approved_steps=False,
    )

    assert verdict == Verdict.UNVERIFIED
    assert unverified_reason is not None
    assert "safety gate 'NO_RESULTS'" in unverified_reason
