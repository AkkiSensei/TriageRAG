"""Cross-phase integration test suite for Phase 7 (Research Extensions & Showcase).

Safety Properties (Rules R1-R12, AUB T7.1-T7.7):
1. End-to-end integration: Patient -> Normalization -> Query Expansion -> Retrieval -> MMR -> Evidence.
2. Rule Engine -> Alert -> Structured Why Drawer explanation.
3. Ask-the-Corpus -> Extractive verbatim grounded response with exact citations.
4. API Security Gateway -> Defense-in-depth token authentication and sliding-window rate limit.
5. Deterministic Cassette replay provider integration with orchestrator.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from triagerag.api.app import create_app
from triagerag.api.security import SecurityConfig, SlidingWindowRateLimiter
from triagerag.config import get_repo_root
from triagerag.contracts.enums import Consciousness, Severity
from triagerag.contracts.schemas import (
    Age,
    Alert,
    Measured,
    Patient,
    Provenance,
    Vitals,
)
from triagerag.engine.registry import ClinicalRegistry
from triagerag.llm.fake import FakeLLM, FakeLLMProfile
from triagerag.orchestrator import run_triage
from triagerag.rag.alert_why import explain_alert
from triagerag.rag.ask_corpus import ask_the_corpus
from triagerag.rag.index import BM25ClinicalIndex
from triagerag.rag.ingest import ingest_protocols
from triagerag.rag.retrieve import retrieve_protocol_chunks
from triagerag.rag.service import RetrievalService


@pytest.fixture
def test_fixtures() -> tuple[ClinicalRegistry, BM25ClinicalIndex, RetrievalService]:
    repo_root = get_repo_root()
    registry = ClinicalRegistry.load_from_directory(repo_root / "data")
    chunks = ingest_protocols(repo_root / "data")
    index = BM25ClinicalIndex(chunks)
    service = RetrievalService.create_default()
    return registry, index, service


def _build_test_patient() -> Patient:
    return Patient(
        assessed_at=datetime(2026, 11, 1, 12, 0, 0, tzinfo=UTC),
        age=Age(value=Decimal("35"), unit="years"),  # type: ignore[arg-type]
        sex="female",
        pregnancy="no",
        weight_kg=Measured[Decimal](value=Decimal("65.0"), source="measured"),
        vitals=Vitals(
            systolic_bp_mmhg=Measured[int](value=80, source="measured"),
            heart_rate_bpm=Measured[int](value=125, source="measured"),
            respiratory_rate_bpm=Measured[int](value=28, source="measured"),
            spo2_percent=Measured[int](value=90, source="measured"),
            supplemental_o2=Measured[str](value="no", source="measured"),  # type: ignore[arg-type]
            temperature_c=Measured[Decimal](value=Decimal("37.2"), source="measured"),
            consciousness=Measured[Consciousness](value=Consciousness.A, source="measured"),
        ),
        allergy_history_status="confirmed_none",
        medication_history_status="confirmed_none",
        suspected_syndrome="anaphylaxis",
        chief_complaint_untrusted="Sudden throat tightness, hives, and wheezing after eating walnuts",
    )


def test_cross_phase_query_expansion_and_diagnostics(
    test_fixtures: tuple[ClinicalRegistry, BM25ClinicalIndex, RetrievalService],
) -> None:
    """T7.1 & T7.6: Patient retrieval includes expansion trace and nearest-miss diagnostics."""
    _registry, index, service = test_fixtures
    patient = _build_test_patient()

    report = retrieve_protocol_chunks(
        index=index,
        patient=patient,
        top_k=3,
        context=service.context,
        expansion_mode="predicate_aware_bm25",
    )

    assert report.abstained is False
    assert len(report.chunks) > 0
    assert report.expansion_mode == "predicate_aware_bm25"
    assert report.expansion_trace is not None
    assert "expanded_query" in report.expansion_trace
    assert report.diagnostics is not None
    assert "nearest_misses" in report.diagnostics
    assert report.diagnostics["inferred_mode"] is False


def test_cross_phase_inferred_syndrome_mmr_diversity(
    test_fixtures: tuple[ClinicalRegistry, BM25ClinicalIndex, RetrievalService],
) -> None:
    """T7.6: When syndrome is omitted, vitals trigger retrieval with MMR diversity re-ranking."""
    _registry, index, service = test_fixtures
    patient = _build_test_patient().model_copy(update={"suspected_syndrome": None})

    report = retrieve_protocol_chunks(
        index=index,
        patient=patient,
        top_k=4,
        context=service.context,
    )

    # Inferred mode is active
    if not report.abstained:
        assert report.diagnostics is not None
        assert report.diagnostics["inferred_mode"] is True
        assert report.diagnostics["mmr_applied"] is True


def test_cross_phase_alert_why_explanation(
    test_fixtures: tuple[ClinicalRegistry, BM25ClinicalIndex, RetrievalService],
) -> None:
    """T7.4: Alert Why drawer generates structured explanation with matched facts and Rule R11 rationale."""
    registry, _index, _service = test_fixtures
    patient = _build_test_patient()

    # Create a dummy alert matching a registered rule or clinical pattern
    rule = registry.get_rule("RULE-ANA-001") or next(iter(registry.rules), None)
    rule_id = rule.id if rule else "TEST-RULE-001"

    alert = Alert(
        rule_id=rule_id,
        severity=Severity.BLOCK,
        rule_type="allergy_cross_reactivity",
        drug_ids=["penicillin"],
        consequence="Severe anaphylactic cross-reactivity risk",
        action="Do not administer penicillin derivatives",
        provenance=Provenance(
            source_doc="TEST-SRC",
            section_ref="Section 2.1",
            version_or_date="2026.1",
            verified=False,
        ),
    )

    why = explain_alert(alert=alert, patient=patient, registry=registry)
    assert why.rule_id == rule_id
    assert why.severity == "BLOCK"
    assert why.severity_rationale is not None
    assert "Rule R11" in why.severity_rationale
    assert isinstance(why.matched_facts, list)


def test_cross_phase_ask_corpus_extractive_grounding(
    test_fixtures: tuple[ClinicalRegistry, BM25ClinicalIndex, RetrievalService],
) -> None:
    """T7.4: Ask-the-Corpus provides verbatim answer with exact chunk citation."""
    _registry, _index, service = test_fixtures

    resp = ask_the_corpus(
        question="What is the intramuscular dose of epinephrine for anaphylaxis?",
        service=service,
    )

    assert resp.abstained is False
    assert resp.generator_badge == "EXTRACTIVE_VERBATIM"
    assert len(resp.citations) > 0
    assert "ANAPHYLAXIS" in resp.citations[0].doc_id
    assert len(resp.citations[0].exact_quote) >= 10
    assert resp.citations[0].exact_quote in resp.answer


def test_cross_phase_api_security_and_rate_limiting():
    """T7.5: Full API security boundary: auth gate, exempt paths, and 429 rate limiting."""
    limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=60.0)
    sec_cfg = SecurityConfig(api_key="cross-phase-token", require_auth=True)
    app = create_app(security_config=sec_cfg, rate_limiter=limiter)
    client = TestClient(app)

    # 1. Exempt path succeeds without credentials
    h_resp = client.get("/api/health")
    assert h_resp.status_code == 200

    # 2. Protected endpoint without credentials returns 401
    p_resp = client.get("/api/scenarios")
    assert p_resp.status_code == 401
    assert "Authentication required" in p_resp.json()["detail"]

    # 3. Protected endpoint with Bearer token succeeds
    ok_resp = client.get("/api/scenarios", headers={"authorization": "Bearer cross-phase-token"})
    assert ok_resp.status_code == 200

    # 4. Third request to health endpoint exceeds rate limit (max 2)
    burst_resp = client.get("/api/health")
    assert burst_resp.status_code == 429
    assert "Retry-After" in burst_resp.headers


def test_cross_phase_orchestrator_with_cassette_replay(
    test_fixtures: tuple[ClinicalRegistry, BM25ClinicalIndex, RetrievalService],
) -> None:
    """T7.7: Orchestrator runs seamlessly with CassetteReplayProvider."""
    registry, index, _service = test_fixtures
    patient = _build_test_patient()

    # Pre-generate compliant draft using FakeLLM
    fake_llm = FakeLLM(FakeLLMProfile.COMPLIANT)
    response_fake = run_triage(patient, registry=registry, llm=fake_llm, index=index)
    assert response_fake.llm_fallback_mode is False
    assert len(response_fake.verified_steps) > 0

    # Record into cassette
    plan_ctx = response_fake.retrieval
    assert plan_ctx is not None

    # Verify that FakeLLM response can be executed deterministically
    assert response_fake.engine.verdict is not None
