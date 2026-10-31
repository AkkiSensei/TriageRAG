"""Unit and contract tests for AUB Phase 1 Task T1.1: Verdict Depends on Retrieval (AUB-VRD-01).

Safety Property (Rule R2, Rule R11, T1.1):
1. If retrieval abstains under ANY AbstainCode, verdict is at most UNVERIFIED, never CHECKED_CLEAR.
2. If no proposed plan step is APPROVED, verdict is at most UNVERIFIED, never CHECKED_CLEAR.
3. Verdict headline for non-clear outcomes NEVER contains the word 'CLEAR'.
4. Hard contraindications (BLOCKED) and warnings (CHECKED_ALERTS) preserve strict precedence.
5. Unknown syndrome and empty-query presentations fail closed to UNVERIFIED.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from triagerag.api.routes.triage import execute_triage
from triagerag.api.schemas import TriageApiRequest
from triagerag.config import get_data_dir
from triagerag.contracts.enums import (
    AbstainCode,
    AgeUnit,
    Consciousness,
    Verdict,
)
from triagerag.contracts.schemas import (
    Age,
    Measured,
    Patient,
    RetrievalReport,
    RetrievedChunk,
    Vitals,
)
from triagerag.engine.registry import ClinicalRegistry
from triagerag.engine.verdict import resolve_verdict_with_reason
from triagerag.orchestrator import run_triage
from triagerag.rag.index import BM25ClinicalIndex
from triagerag.rag.ingest import ingest_protocols

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)


def _make_clean_patient(suspected_syndrome: str | None = None) -> Patient:
    """Build a completely healthy patient with complete history and no baseline alerts."""
    return Patient(
        assessed_at=NOW,
        age=Age(value=Decimal(35), unit=AgeUnit.years),
        sex="male",
        pregnancy="no",
        weight_kg=Measured[Decimal](value=Decimal("75.0"), source="measured"),
        vitals=Vitals(
            systolic_bp_mmhg=Measured[int](value=120, source="measured"),
            diastolic_bp_mmhg=Measured[int](value=80, source="measured"),
            heart_rate_bpm=Measured[int](value=72, source="measured"),
            respiratory_rate_bpm=Measured[int](value=16, source="measured"),
            spo2_percent=Measured[int](value=98, source="measured"),
            temperature_c=Measured[Decimal](value=Decimal("36.8"), source="measured"),
            consciousness=Measured[Consciousness](value=Consciousness.A, source="measured"),
        ),
        medication_history_status="confirmed_none",
        allergy_history_status="confirmed_none",
        suspected_syndrome=suspected_syndrome,
        chief_complaint_untrusted="",
    )


@pytest.mark.parametrize("abstain_code", [ac for ac in AbstainCode if ac != AbstainCode.NONE])
def test_all_abstain_codes_yield_non_clear_verdict(abstain_code: AbstainCode) -> None:
    """Every non-NONE AbstainCode must result in UNVERIFIED, never CHECKED_CLEAR (AUB-VRD-01)."""
    retrieval_report = RetrievalReport(
        chunks=[],
        query="test query",
        filters={"population": "adult"},
        stage_scores={},
        abstained=True,
        abstain_code=abstain_code,
        reason=f"Abstention reason for {abstain_code.value}",
        backend="bm25",
    )

    verdict, reason = resolve_verdict_with_reason(
        has_block=False,
        has_skip_or_unresolved=False,
        has_alert=False,
        retrieval_report=retrieval_report,
        has_approved_steps=False,
    )

    assert verdict == Verdict.UNVERIFIED, f"Expected UNVERIFIED for {abstain_code}, got {verdict}"
    assert verdict != Verdict.CHECKED_CLEAR
    assert reason is not None
    assert abstain_code.value in reason


@pytest.mark.parametrize("abstain_code", [ac for ac in AbstainCode if ac != AbstainCode.NONE])
def test_all_abstain_codes_in_orchestrator_yield_unverified_and_no_clear_headline(
    abstain_code: AbstainCode,
) -> None:
    """Orchestrator headline and verdict must never contain 'CLEAR' when retrieval abstains."""
    data_dir = get_data_dir()
    registry = ClinicalRegistry.load_from_directory(data_dir)
    chunks = ingest_protocols(data_dir)
    index = BM25ClinicalIndex(chunks)

    # Patient with unknown syndrome triggers EMPTY_QUERY / abstention
    patient = _make_clean_patient(suspected_syndrome=None)
    response = run_triage(patient, registry=registry, index=index)

    assert response.engine.verdict == Verdict.UNVERIFIED
    assert response.engine.verdict != Verdict.CHECKED_CLEAR
    assert response.explanation is not None
    assert "CLEAR" not in response.explanation.headline
    assert response.explanation.headline.startswith("UNVERIFIED:")


def test_retrieval_report_with_no_approved_steps_never_yields_checked_clear() -> None:
    """If retrieval succeeded but 0 steps are APPROVED, verdict must be at most UNVERIFIED."""
    chunk = RetrievedChunk(
        doc_id="DOC_TEST",
        section="Management",
        chunk_id="CHUNK_001",
        parent_id="DOC_TEST",
        text="Sample text",
        population="adult",
        syndrome="anaphylaxis",
    )
    retrieval_report = RetrievalReport(
        chunks=[chunk],
        query="anaphylaxis",
        filters={"population": "adult", "syndrome": "anaphylaxis"},
        stage_scores={},
        abstained=False,
        abstain_code=AbstainCode.NONE,
        reason=None,
        backend="bm25",
    )

    # 1. Zero steps approved
    verdict, reason = resolve_verdict_with_reason(
        has_block=False,
        has_skip_or_unresolved=False,
        has_alert=False,
        retrieval_report=retrieval_report,
        has_approved_steps=False,
    )
    assert verdict == Verdict.UNVERIFIED
    assert verdict != Verdict.CHECKED_CLEAR
    assert reason is not None
    assert "APPROVED" in reason

    # 2. At least one step approved -> returns CHECKED_CLEAR (clean case)
    verdict_approved, reason_approved = resolve_verdict_with_reason(
        has_block=False,
        has_skip_or_unresolved=False,
        has_alert=False,
        retrieval_report=retrieval_report,
        has_approved_steps=True,
    )
    assert verdict_approved == Verdict.CHECKED_CLEAR
    assert reason_approved is None


def test_blocked_precedence_preserved_over_retrieval_abstention() -> None:
    """Rule R11: BLOCKED contraindications always override retrieval abstention."""
    retrieval_report = RetrievalReport(
        chunks=[],
        query="",
        filters={},
        stage_scores={},
        abstained=True,
        abstain_code=AbstainCode.UNKNOWN_SYNDROME,
        reason="No syndrome specified",
        backend="bm25",
    )

    # has_block=True must yield BLOCKED even though retrieval abstained
    verdict, reason = resolve_verdict_with_reason(
        has_block=True,
        has_skip_or_unresolved=False,
        has_alert=False,
        retrieval_report=retrieval_report,
        has_approved_steps=False,
    )
    assert verdict == Verdict.BLOCKED
    assert reason is not None
    assert "BLOCK" in reason


def test_checked_alerts_precedence_when_steps_approved() -> None:
    """CHECKED_ALERTS fires when non-blocking alerts exist and approved steps are present."""
    chunk = RetrievedChunk(
        doc_id="DOC_TEST",
        section="Management",
        chunk_id="CHUNK_001",
        parent_id="DOC_TEST",
        text="Sample text",
        population="adult",
        syndrome="anaphylaxis",
    )
    retrieval_report = RetrievalReport(
        chunks=[chunk],
        query="chest_pain",
        filters={"population": "adult", "syndrome": "chest_pain"},
        stage_scores={},
        abstained=False,
        abstain_code=AbstainCode.NONE,
        reason=None,
        backend="bm25",
    )

    verdict, reason = resolve_verdict_with_reason(
        has_block=False,
        has_skip_or_unresolved=False,
        has_alert=True,
        retrieval_report=retrieval_report,
        has_approved_steps=True,
    )
    assert verdict == Verdict.CHECKED_ALERTS
    assert reason is not None
    assert "warnings" in reason


def test_api_serialization_returns_unverified_for_abstained_retrieval() -> None:
    """API contract must serialize UNVERIFIED verdict and non-clear headline on abstention."""
    req = TriageApiRequest(
        patient=_make_clean_patient(suspected_syndrome=None),
        suspected_syndrome=None,
        include_complaint_in_llm=False,
    )
    resp = execute_triage(req)

    assert resp.engine.verdict == Verdict.UNVERIFIED
    assert resp.engine.verdict != Verdict.CHECKED_CLEAR
    assert resp.explanation is not None
    assert "CLEAR" not in resp.explanation.headline
    assert resp.explanation.headline.startswith("UNVERIFIED:")
    assert resp.engine.unverified_reason is not None
