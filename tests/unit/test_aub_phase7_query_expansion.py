"""Unit tests for Controlled Query Expansion (T7.1 / AUB-EXP-01).

Safety Properties (Rules R1, R2, R3, R7, R12):
1. Query expansion is purely deterministic and traceable to satisfied patient predicates.
2. chief_complaint_untrusted is NEVER included in expansion.
3. Unknown or indeterminate patient predicates are NEVER expanded.
4. Every expansion term carries explicit predicate origin provenance.
5. Baseline BM25, predicate-aware BM25, and controlled expansion remain separately selectable.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from triagerag.contracts.enums import Consciousness
from triagerag.contracts.schemas import Age, Measured, Patient, Vitals
from triagerag.rag.index import BM25ClinicalIndex
from triagerag.rag.ingest import ingest_protocols
from triagerag.rag.query_expansion import (
    QueryExpansionConfig,
    build_expanded_query,
    load_query_expansion_config,
)
from triagerag.rag.retrieve import (
    build_retrieval_context,
    build_retrieval_query,
    retrieve_protocol_chunks,
)


def _build_test_patient(
    hr: Decimal | None = Decimal("130"),
    sbp: Decimal | None = Decimal("75"),
    spo2: Decimal | None = Decimal("88"),
    glucose: Decimal | None = Decimal("40"),
    temp: Decimal | None = Decimal("39.2"),
    syndrome: str = "anaphylaxis",
) -> Patient:
    vitals = Vitals(
        heart_rate_bpm=Measured(value=hr, source="measured" if hr is not None else "unknown"),
        systolic_bp_mmhg=Measured(value=sbp, source="measured" if sbp is not None else "unknown"),
        spo2_percent=Measured(value=spo2, source="measured" if spo2 is not None else "unknown"),
        blood_glucose_mg_dl=Measured(
            value=glucose, source="measured" if glucose is not None else "unknown"
        ),
        temperature_c=Measured(value=temp, source="measured" if temp is not None else "unknown"),
        consciousness=Measured(value=Consciousness.A, source="measured"),
    )
    return Patient(
        assessed_at=datetime.now(UTC),
        age=Age(value=35, unit="years"),
        sex="female",
        pregnancy="no",
        weight_kg=Measured(value=Decimal("70.0"), source="measured"),
        allergy_history_status="confirmed_none",
        medication_history_status="confirmed_none",
        suspected_syndrome=syndrome,
        vitals=vitals,
        chief_complaint_untrusted="UNTRUSTED COMPLAINT: DO NOT USE FOR QUERY EXPANSION",
    )


def test_query_expansion_config_loading_and_schema() -> None:
    """T7.1: Verify query expansion vocabulary loads with valid schema and provenance."""
    cfg = load_query_expansion_config()
    assert isinstance(cfg, QueryExpansionConfig)
    assert cfg.source_status == "SYNTHETIC_AUTHORED"
    assert "low_systolic_bp" in cfg.expansions
    assert "hypoxemia" in cfg.expansions
    assert len(cfg.expansions["low_systolic_bp"].terms) >= 2


def test_baseline_bm25_mode_does_not_expand() -> None:
    """T7.1: baseline_bm25 mode preserves base query with zero expansion terms."""
    ctx = build_retrieval_context()
    patient = _build_test_patient()
    base_query, _ = build_retrieval_query(patient, context=ctx)

    res = build_expanded_query(patient, ctx, base_query, mode="baseline_bm25")
    assert res.mode == "baseline_bm25"
    assert res.original_query == base_query
    assert res.expanded_query == base_query
    assert res.expansion_terms == []
    assert res.predicate_origins == {}


def test_controlled_expansion_mode_expands_satisfied_predicates() -> None:
    """T7.1: controlled_expansion mode adds targeted protocol terms from satisfied predicates."""
    ctx = build_retrieval_context()
    # Patient has low SBP (75), low SpO2 (88), hypoglycemia (40), and tachycardia (130)
    patient = _build_test_patient()
    base_query, _ = build_retrieval_query(patient, context=ctx)

    res = build_expanded_query(patient, ctx, base_query, mode="controlled_expansion")
    assert res.mode == "controlled_expansion"
    assert res.original_query == base_query
    assert len(res.expansion_terms) > 0

    # Terms must be traceable to satisfied predicates
    assert "low_systolic_bp" in res.predicate_origins
    assert "hypoxemia" in res.predicate_origins
    assert "hypoglycemia" in res.predicate_origins

    # Check that expansion terms are present in expanded query string
    for term in res.expansion_terms:
        assert term in res.expanded_query

    # Untrusted chief complaint must NEVER appear in expanded query
    assert "untrusted" not in res.expanded_query.lower()
    assert "complaint" not in res.expanded_query.lower()


def test_unknown_predicates_are_never_expanded() -> None:
    """T7.1 / Rule R2: Unknown or indeterminate vitals predicates are strictly skipped from expansion."""
    ctx = build_retrieval_context()
    # Patient with unknown SBP, unknown SpO2, unknown Glucose
    patient = _build_test_patient(hr=Decimal("80"), sbp=None, spo2=None, glucose=None)
    base_query, _ = build_retrieval_query(patient, context=ctx)

    res = build_expanded_query(patient, ctx, base_query, mode="controlled_expansion")
    # low_systolic_bp, hypoxemia, hypoglycemia must be in unknown_predicates_skipped
    assert "low_systolic_bp" in res.unknown_predicates_skipped
    assert "hypoxemia" in res.unknown_predicates_skipped
    assert "hypoglycemia" in res.unknown_predicates_skipped

    # Must NOT be in predicate origins
    assert "low_systolic_bp" not in res.predicate_origins
    assert "hypoxemia" not in res.predicate_origins
    assert "hypoglycemia" not in res.predicate_origins


def test_retrieve_protocol_chunks_expansion_integration() -> None:
    """T7.1: retrieve_protocol_chunks honors expansion_mode and attaches expansion_trace."""
    ctx = build_retrieval_context()
    chunks = ingest_protocols(ctx.data_dir)
    index = BM25ClinicalIndex(chunks)

    patient = _build_test_patient(syndrome="anaphylaxis")

    # 1. Default mode: predicate_aware_bm25
    report_default = retrieve_protocol_chunks(patient, index, context=ctx)
    assert report_default.expansion_mode == "predicate_aware_bm25"
    assert report_default.expansion_trace is not None
    assert report_default.expansion_trace["mode"] == "predicate_aware_bm25"

    # 2. Controlled expansion mode
    report_expanded = retrieve_protocol_chunks(
        patient, index, context=ctx, expansion_mode="controlled_expansion"
    )
    assert report_expanded.expansion_mode == "controlled_expansion"
    assert report_expanded.expansion_trace is not None
    assert report_expanded.expansion_trace["mode"] == "controlled_expansion"
    assert len(report_expanded.expansion_trace["expansion_terms"]) > 0
    assert not report_expanded.abstained
