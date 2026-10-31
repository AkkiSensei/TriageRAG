"""Unit tests for reachable vitals-only syndrome inference (AUB Phase 2 Task T2.7).

Safety Properties (Rule R1, R2, R3, R11, HD-4, AUB Task T2.7):
1. Vitals-only presentations can infer candidate emergency syndrome from structured predicates.
2. Inferred syndrome returns AbstainCode.SYNDROME_INFERRED with abstained=False when margin passes.
3. Returned protocol chunks are restricted strictly to the winning inferred syndrome.
4. HD-4 Clinical Governance: Inferred syndrome plan steps CAN NEVER reach StepStatus.APPROVED;
   they are strictly capped at StepStatus.REQUIRES_CLINICIAN_CONFIRMATION.
5. Ambiguous multi-syndrome matches fail closed with AbstainCode.AMBIGUOUS_MARGIN.
6. Normal vitals or empty presentations without suspected syndrome fail closed with EMPTY_QUERY.
7. Vitals-only benchmark Recall@1 and Recall@5 are strictly > 0.0 and reported with CIs.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from triagerag.config import get_data_dir
from triagerag.contracts.enums import (
    AbstainCode,
    AgeUnit,
    Consciousness,
    StepStatus,
)
from triagerag.contracts.schemas import (
    Age,
    Measured,
    Patient,
    Vitals,
)
from triagerag.engine.registry import load_registry
from triagerag.orchestrator import run_triage
from triagerag.rag.index import BM25ClinicalIndex
from triagerag.rag.ingest import ingest_protocols
from triagerag.rag.retrieve import retrieve_protocol_chunks
from triagerag.rag.service import RetrievalService

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)


def _make_vitals_patient(
    *,
    age_years: int = 35,
    sbp: int | None = None,
    hr: int | None = None,
    rr: int | None = None,
    spo2: int | None = None,
    temp_c: str | None = None,
    bg_mg_dl: str | None = None,
    consciousness: Consciousness | None = Consciousness.A,
    syndrome: str | None = None,
) -> Patient:
    """Helper to build a structured synthetic Patient for retrieval tests."""
    return Patient(
        assessed_at=NOW,
        age=Age(value=Decimal(str(age_years)), unit=AgeUnit.years),
        sex="female",
        pregnancy="no",
        weight_kg=Measured[Decimal](value=Decimal("65.0"), source="measured"),
        vitals=Vitals(
            systolic_bp_mmhg=(
                Measured[int](value=sbp, source="measured") if sbp is not None else Measured[int]()
            ),
            heart_rate_bpm=(
                Measured[int](value=hr, source="measured") if hr is not None else Measured[int]()
            ),
            respiratory_rate_bpm=(
                Measured[int](value=rr, source="measured") if rr is not None else Measured[int]()
            ),
            spo2_percent=(
                Measured[int](value=spo2, source="measured")
                if spo2 is not None
                else Measured[int]()
            ),
            temperature_c=(
                Measured[Decimal](value=Decimal(temp_c), source="measured")
                if temp_c is not None
                else Measured[Decimal]()
            ),
            blood_glucose_mg_dl=(
                Measured[Decimal](value=Decimal(bg_mg_dl), source="measured")
                if bg_mg_dl is not None
                else Measured[Decimal]()
            ),
            consciousness=(
                Measured[Consciousness](value=consciousness, source="measured")
                if consciousness is not None
                else Measured[Consciousness]()
            ),
        ),
        medication_history_status="confirmed_none",
        medications=[],
        allergy_history_status="confirmed_nkda",
        allergies=[],
        renal_impairment="no",
        hepatic_impairment="no",
        suspected_syndrome=syndrome,
        chief_complaint_untrusted="",
    )


@pytest.fixture(scope="module")
def default_index() -> BM25ClinicalIndex:
    data_dir = get_data_dir()
    chunks = ingest_protocols(data_dir)
    return BM25ClinicalIndex(chunks)


def test_vitals_only_anaphylaxis_returns_syndrome_inferred(
    default_index: BM25ClinicalIndex,
) -> None:
    """T2.7: Vitals-only anaphylaxis presentation infers anaphylaxis with SYNDROME_INFERRED."""
    # Classic anaphylaxis shock presentation: profound hypotension and compensatory tachycardia
    patient = _make_vitals_patient(
        sbp=65,
        hr=125,
        rr=22,
        spo2=95,
        consciousness=Consciousness.A,
        syndrome=None,
    )

    report = retrieve_protocol_chunks(patient, default_index)

    assert report.abstained is False
    assert report.abstain_code == AbstainCode.SYNDROME_INFERRED
    assert report.reason is not None
    assert "anaphylaxis" in report.reason.lower()
    assert len(report.chunks) > 0
    assert all(c.syndrome == "anaphylaxis" for c in report.chunks)
    assert report.filters.get("inferred_syndrome") == "anaphylaxis"


def test_inferred_syndrome_requires_clinician_confirmation_gate(
    default_index: BM25ClinicalIndex,
) -> None:
    """HD-4 Fail-Closed Gate: Inferred syndrome steps can NEVER reach StepStatus.APPROVED."""
    registry = load_registry(get_data_dir())

    patient = _make_vitals_patient(
        sbp=65,
        hr=125,
        rr=22,
        spo2=95,
        consciousness=Consciousness.A,
        syndrome=None,
    )

    response = run_triage(patient, registry=registry, index=default_index)

    assert response.retrieval is not None
    assert response.retrieval.abstain_code == AbstainCode.SYNDROME_INFERRED
    assert response.retrieval.abstained is False

    # Under HD-4, no inferred syndrome step may ever be approved without clinician entry
    if response.verified_steps:
        for step in response.verified_steps:
            assert step.status != StepStatus.APPROVED
            assert step.status == StepStatus.REQUIRES_CLINICIAN_CONFIRMATION
            assert any("SYNDROME_INFERRED" in r for r in step.rejection_reasons)


def test_ambiguous_vitals_presentation_abstains_with_ambiguous_margin(
    default_index: BM25ClinicalIndex,
) -> None:
    """T2.7 / RAG-01: Isolated abnormal vitals without clear syndrome margin fail closed."""
    # Isolated hypotension without tachycardia, wheezing, or hypoxia matches multiple protocols
    ambiguous_patient = _make_vitals_patient(
        sbp=80,
        hr=72,
        rr=16,
        spo2=98,
        consciousness=Consciousness.A,
        syndrome=None,
    )

    report = retrieve_protocol_chunks(ambiguous_patient, default_index)

    assert report.abstained is True
    assert report.abstain_code == AbstainCode.AMBIGUOUS_MARGIN
    assert report.chunks == []
    assert report.reason is not None
    assert "ambiguous syndrome match" in report.reason.lower()


def test_normal_vitals_without_syndrome_abstains_empty_query(
    default_index: BM25ClinicalIndex,
) -> None:
    """T2.7 / R2: Healthy/normal vitals with no suspected syndrome fail closed as EMPTY_QUERY."""
    normal_patient = _make_vitals_patient(
        sbp=120,
        hr=72,
        rr=16,
        spo2=98,
        temp_c="36.8",
        consciousness=Consciousness.A,
        syndrome=None,
    )

    report = retrieve_protocol_chunks(normal_patient, default_index)

    assert report.abstained is True
    assert report.abstain_code == AbstainCode.EMPTY_QUERY
    assert report.chunks == []


def test_empty_vitals_without_syndrome_abstains_empty_query(
    default_index: BM25ClinicalIndex,
) -> None:
    """T2.7 / R2: Missing/unmeasured vitals with no suspected syndrome abstain as EMPTY_QUERY."""
    empty_patient = _make_vitals_patient(
        sbp=None,
        hr=None,
        rr=None,
        spo2=None,
        consciousness=None,
        syndrome=None,
    )

    report = retrieve_protocol_chunks(empty_patient, default_index)

    assert report.abstained is True
    assert report.abstain_code == AbstainCode.EMPTY_QUERY
    assert report.chunks == []


def test_vitals_only_benchmark_metrics_positive_and_zero_wrong_protocol() -> None:
    """T2.7 / Acceptance: Vitals-only benchmark Recall@k > 0 and wrong_protocol_rate == 0."""
    from eval.run_retrieval import run_retrieval_benchmark

    summary = run_retrieval_benchmark(backend="bm25", write_reports=False)
    test_metrics = summary["test"]
    vit_metrics = test_metrics["vitals_only"]

    # Vitals-only Recall@1 and Recall@5 must be non-zero
    assert vit_metrics["recall_at_1"] > 0.0
    assert vit_metrics["recall_at_5"] > 0.0
    assert vit_metrics["recall_at_1"] >= 50.0

    # Wrong protocol rate must stay at 0.0 (gate check)
    assert test_metrics["wrong_protocol_rate"] == 0.0
    assert test_metrics["abstain_recall_hard_negatives"] == 1.0


def test_retrieval_service_explain_exposes_inferred_syndrome_diagnostics() -> None:
    """T2.7 / Explainability: RetrievalService.explain transparently exposes inference trace."""
    service = RetrievalService.create_default(get_data_dir(), backend="bm25")

    patient = _make_vitals_patient(
        sbp=65,
        hr=125,
        rr=22,
        spo2=95,
        consciousness=Consciousness.A,
        syndrome=None,
    )

    explanation = service.explain(patient)

    assert explanation["abstained"] is False
    assert explanation["abstain_code"] == AbstainCode.SYNDROME_INFERRED.value
    assert "anaphylaxis" in explanation["reason"].lower()
    assert len(explanation["retrieved_chunks"]) > 0
    assert explanation["retrieved_chunks"][0]["syndrome"] == "anaphylaxis"
