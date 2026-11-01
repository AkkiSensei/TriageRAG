"""Unit tests for Alert "Why?" drawer and Ask-the-Corpus extractive Q&A (T7.4 / AUB-QA-01).

Safety Properties (Rules R1, R2, R3, R7, R8, R11, R12):
1. Purely extractive: Statements are extracted verbatim from retrieved protocol chunks.
2. Zero invented facts: Numbers, doses, and routes are preserved exactly; no synthetic dose math.
3. Fail-closed abstention: If no chunk has sufficient lexical support, abstains immediately.
4. Untrusted input protection: User question cannot alter registry rules, trust mode, or system prompts.
5. Strict provenance: Every answer includes source chunk ID, doc ID, section, and license tag.
6. Alert Why drawer: Distinguishes confirmed patient facts from unknown facts and explains R11 severity rationale.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient

from triagerag.api.app import create_app
from triagerag.contracts.enums import Consciousness, Severity, SourceStatus
from triagerag.contracts.schemas import (
    Age,
    Alert,
    AllergyEntry,
    Measured,
    Patient,
    Provenance,
    Vitals,
)
from triagerag.engine.registry import load_registry
from triagerag.rag.alert_why import explain_alert
from triagerag.rag.ask_corpus import ask_the_corpus

client = TestClient(create_app())


def _build_test_patient() -> Patient:
    vitals = Vitals(
        heart_rate_bpm=Measured(value=Decimal("120"), source="measured"),
        systolic_bp_mmhg=Measured(value=Decimal("80"), source="measured"),
        spo2_percent=Measured(value=Decimal("91"), source="measured"),
        blood_glucose_mg_dl=Measured(value=None, source="unknown"),
        temperature_c=Measured(value=Decimal("38.5"), source="measured"),
        consciousness=Measured(value=Consciousness.A, source="measured"),
    )
    allergies = [
        AllergyEntry(
            raw_substance="penicillin",
            reaction_type="anaphylaxis_ige",
            resolved=True,
        )
    ]
    return Patient(
        assessed_at=datetime.now(UTC),
        age=Age(value=40, unit="years"),
        sex="male",
        pregnancy="no",
        weight_kg=Measured(value=Decimal("75.0"), source="measured"),
        allergy_history_status="confirmed_list",
        allergies=allergies,
        medication_history_status="confirmed_none",
        suspected_syndrome="anaphylaxis",
        vitals=vitals,
        chief_complaint_untrusted="Severe shortness of breath and facial swelling",
    )


def test_ask_the_corpus_extracts_verbatim_statement_with_citation() -> None:
    """T7.4: Ask-the-Corpus returns verbatim text with exact chunk citation."""
    res = ask_the_corpus(question="What is the treatment for anaphylaxis?", population="adult")
    assert not res.abstained
    assert len(res.citations) > 0
    cit = res.citations[0]
    assert cit.chunk_id
    assert cit.doc_id
    assert cit.license
    assert cit.exact_quote in res.answer
    assert res.generator_badge == "EXTRACTIVE_VERBATIM"


def test_ask_the_corpus_abstains_on_empty_or_gibberish_question() -> None:
    """T7.4 / Rule R2: Empty or unsupported questions fail-closed with abstention."""
    # 1. Empty question
    res_empty = ask_the_corpus(question="")
    assert res_empty.abstained
    assert res_empty.abstain_reason is not None and "too short" in res_empty.abstain_reason.lower()

    # 2. Random gibberish question with zero clinical terms
    res_gibberish = ask_the_corpus(question="xyzabc qqqqqq zzzz")
    assert res_gibberish.abstained


def test_ask_the_corpus_endpoint() -> None:
    """T7.4: POST /api/corpus/ask returns structured response over HTTP."""
    resp = client.post(
        "/api/corpus/ask",
        json={"question": "epinephrine anaphylaxis intramuscular", "population": "adult"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "citations" in data
    assert "generator_badge" in data
    assert data["generator_badge"] == "EXTRACTIVE_VERBATIM"


def test_alert_why_drawer_distinguishes_matched_and_unknown_facts() -> None:
    """T7.4: explain_alert exposes matched facts, unknown vitals, and BLOCK rationale."""
    patient = _build_test_patient()
    registry = load_registry()

    prov = Provenance(
        source_doc="TEST_WHY",
        section_ref="SEC_WHY",
        version_or_date="2026",
        source_status=SourceStatus.REVIEWED,
        content_origin="AGENT_DRAFT_SYNTHETIC",
        verified=False,
    )
    alert = Alert(
        rule_id="ALLERGY_PENICILLIN_CEPH_R1_SIMILAR",
        severity=Severity.BLOCK,
        rule_type="allergy_cross_reactivity",
        drug_ids=["amoxicillin"],
        consequence="Severe anaphylactic reaction due to amino-side-chain cross-reactivity",
        action="Select non-cross-reactive alternative agent",
        provenance=prov,
        unverified=True,
    )

    explanation = explain_alert(alert, patient, registry)
    assert explanation.rule_id == "ALLERGY_PENICILLIN_CEPH_R1_SIMILAR"
    assert explanation.severity == "BLOCK"
    assert "no clinician override is permitted for BLOCK alerts" in explanation.severity_rationale

    # Matched facts
    assert any("amoxicillin" in f for f in explanation.matched_facts)
    assert any("penicillin" in f for f in explanation.matched_facts)

    # Unknown facts: blood_glucose_mg_dl was unmeasured
    assert any("blood_glucose_mg_dl" in u for u in explanation.unknown_facts)


def test_alert_why_endpoint() -> None:
    """T7.4: POST /api/triage/alert-why returns 200 with structured explanation."""
    patient = _build_test_patient()
    prov = Provenance(
        source_doc="TEST_WHY_API",
        section_ref="SEC_WHY_API",
        version_or_date="2026",
        source_status=SourceStatus.REVIEWED,
        content_origin="AGENT_DRAFT_SYNTHETIC",
        verified=False,
    )
    alert = Alert(
        rule_id="ALLERGY_PENICILLIN_CEPH_R1_SIMILAR",
        severity=Severity.BLOCK,
        rule_type="allergy_cross_reactivity",
        drug_ids=["amoxicillin"],
        consequence="Severe reaction",
        action="Do not administer",
        provenance=prov,
        unverified=True,
    )

    payload = {
        "alert": alert.model_dump(mode="json"),
        "patient": patient.model_dump(mode="json"),
    }
    resp = client.post("/api/triage/alert-why", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["rule_id"] == "ALLERGY_PENICILLIN_CEPH_R1_SIMILAR"
    assert "matched_facts" in data
    assert "unknown_facts" in data
    assert "severity_rationale" in data
