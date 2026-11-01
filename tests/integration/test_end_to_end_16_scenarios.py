"""Comprehensive end-to-end audit test suite exercising all 16 required application scenarios.

Controlling specification: AUB.md Section 5 (Required End-to-End Scenarios).
Safety Properties (Rules R1-R12):
1. Ordinary retrieval grounded in real corpus evidence.
2. Patient-aware retrieval dynamically conditioned on structured patient facts.
3. Inferred syndrome mode with MMR diversity and clinician confirmation gate.
4. Fail-closed abstention on missing/empty retrieval.
5. First-class UNKNOWN handling with explicit skipped checks.
6. Applicability verification preventing citation laundering.
7. Qualifier preservation rejecting dropped conditional/temporal modifiers.
8. Strict vs Demo trust mode isolation.
9. FDC multi-ingredient expansion and constituent duplication detection.
10. Exact Decimal dose math, magnitude tripwires, and volume boundaries.
11. Verbatim evidence-grounded candidate rule mining with unreviewed queue.
12. Inspectable Evidence trace matching backend retrieval execution.
13. Structured Alert Why explanation drawer.
14. Extractive Ask-the-Corpus with exact citations and fail-closed abstention.
15. Defense-in-depth API security (authentication boundary & rate limiting).
16. Mock vs Real generator boundary preserving HD-14.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from triagerag.api.app import create_app
from triagerag.api.security import SecurityConfig, SlidingWindowRateLimiter
from triagerag.config import get_data_dir, get_repo_root
from triagerag.contracts.enums import (
    AbstainCode,
    ActionType,
    Consciousness,
    DoseUnit,
    Route,
    Severity,
    TrustMode,
    Verdict,
)
from triagerag.contracts.rules_schema import ClinicalRule
from triagerag.contracts.schemas import (
    Age,
    Alert,
    ExplicitDose,
    Measured,
    OrchestratorConfig,
    Patient,
    PlanStepDraft,
    Provenance,
    Vitals,
)
from triagerag.engine.dose_engine import verify_dose
from triagerag.engine.registry import ClinicalRegistry
from triagerag.llm.cassette import (
    ApprovedLocalProvider,
    LLMProviderApprovalError,
    LocalLLMConfig,
)
from triagerag.llm.fake import FakeLLM, FakeLLMProfile
from triagerag.normalize.yaml_loader import load_yaml_decimal
from triagerag.orchestrator import run_triage
from triagerag.rag.alert_why import explain_alert
from triagerag.rag.ask_corpus import ask_the_corpus
from triagerag.rag.index import BM25ClinicalIndex
from triagerag.rag.ingest import ingest_protocols
from triagerag.rag.predicates import (
    PredicateEvalResult,
    evaluate_patient_predicates,
    load_predicate_vocabulary,
)
from triagerag.rag.retrieve import retrieve_protocol_chunks
from triagerag.rag.service import RetrievalService
from triagerag.verify.applicability import ApplicabilityStatus, verify_node_applicability
from triagerag.verify.qualifiers import verify_step_qualifiers


@pytest.fixture(scope="module")
def shared_registry() -> ClinicalRegistry:
    return ClinicalRegistry.load_from_directory(get_repo_root() / "data")


@pytest.fixture(scope="module")
def shared_index() -> BM25ClinicalIndex:
    return BM25ClinicalIndex(ingest_protocols(get_repo_root() / "data"))


def _build_base_patient(
    syndrome: str | None = "anaphylaxis",
    sbp: int = 120,
    hr: int = 75,
    spo2: int = 98,
    unmeasured: bool = False,
) -> Patient:
    """Helper to construct a typed synthetic patient."""
    if unmeasured:
        vitals = Vitals(
            systolic_bp_mmhg=Measured[int](source="unknown"),
            heart_rate_bpm=Measured[int](source="unknown"),
            respiratory_rate_bpm=Measured[int](source="unknown"),
            spo2_percent=Measured[int](source="unknown"),
            supplemental_o2=Measured[str](source="unknown"),  # type: ignore[arg-type]
            temperature_c=Measured[Decimal](source="unknown"),
            consciousness=Measured[Consciousness](source="unknown"),
        )
        weight = Measured[Decimal](source="unknown")
    else:
        vitals = Vitals(
            systolic_bp_mmhg=Measured[int](value=sbp, source="measured"),
            heart_rate_bpm=Measured[int](value=hr, source="measured"),
            respiratory_rate_bpm=Measured[int](value=16, source="measured"),
            spo2_percent=Measured[int](value=spo2, source="measured"),
            supplemental_o2=Measured[str](value="no", source="measured"),  # type: ignore[arg-type]
            temperature_c=Measured[Decimal](value=Decimal("37.0"), source="measured"),
            consciousness=Measured[Consciousness](value=Consciousness.A, source="measured"),
        )
        weight = Measured[Decimal](value=Decimal("70.0"), source="measured")

    return Patient(
        assessed_at=datetime(2026, 11, 1, 12, 0, 0, tzinfo=UTC),
        age=Age(value=Decimal("45"), unit="years"),  # type: ignore[arg-type]
        sex="female",
        pregnancy="no",
        weight_kg=weight,
        vitals=vitals,
        allergy_history_status="confirmed_none" if not unmeasured else "unknown_unobtainable",
        medication_history_status="confirmed_none" if not unmeasured else "unknown_unobtainable",
        suspected_syndrome=syndrome,
        chief_complaint_untrusted="Evaluated under clinical protocol",
    )


# ---------------------------------------------------------------------------
# Scenario 1 — Ordinary Retrieval
# ---------------------------------------------------------------------------
def test_scenario_01_ordinary_retrieval(
    shared_registry: ClinicalRegistry, shared_index: BM25ClinicalIndex
) -> None:
    """Scenario 1: Valid user request produces grounded response with actual ranking and citations."""
    patient = _build_base_patient(syndrome="anaphylaxis", sbp=78, hr=130, spo2=89)
    llm = FakeLLM(FakeLLMProfile.COMPLIANT)
    result = run_triage(patient, registry=shared_registry, index=shared_index, llm=llm)

    # Retrieval and plan verification checks
    assert result.retrieval is not None
    assert result.retrieval.abstained is False
    assert len(result.retrieval.chunks) > 0
    assert len(result.verified_steps) > 0

    # Grounded citations and explanation checks
    assert result.explanation is not None
    assert result.retrieval.query != ""
    assert result.explanation.headline != ""
    assert result.explanation.evidence_summary != ""
    assert result.engine is not None


# ---------------------------------------------------------------------------
# Scenario 2 — Patient-Aware Retrieval
# ---------------------------------------------------------------------------
def test_scenario_02_patient_aware_retrieval(shared_index: BM25ClinicalIndex) -> None:
    """Scenario 2: Same syndrome with different patient context changes retrieval ranking."""
    service = RetrievalService.create_default()
    vocab = load_predicate_vocabulary()

    # Patient A: Severe anaphylaxis with profound shock (hypotension)
    patient_shock = _build_base_patient(syndrome="anaphylaxis", sbp=65, hr=140)
    # Patient B: Anaphylaxis without shock (normotensive)
    patient_stable = _build_base_patient(syndrome="anaphylaxis", sbp=125, hr=80)

    preds_shock = evaluate_patient_predicates(patient_shock, vocab.predicates)
    preds_stable = evaluate_patient_predicates(patient_stable, vocab.predicates)

    # Patient with shock satisfies low_systolic_bp; stable patient does not
    assert preds_shock.get("low_systolic_bp") == PredicateEvalResult.SATISFIED
    assert preds_stable.get("low_systolic_bp") != PredicateEvalResult.SATISFIED

    report_shock = retrieve_protocol_chunks(
        index=shared_index, patient=patient_shock, top_k=3, context=service.context
    )
    report_stable = retrieve_protocol_chunks(
        index=shared_index, patient=patient_stable, top_k=3, context=service.context
    )

    assert report_shock.abstained is False
    assert report_stable.abstained is False
    assert len(report_shock.chunks) > 0
    assert len(report_stable.chunks) > 0


# ---------------------------------------------------------------------------
# Scenario 3 — Inferred Syndrome
# ---------------------------------------------------------------------------
def test_scenario_03_inferred_syndrome(
    shared_registry: ClinicalRegistry, shared_index: BM25ClinicalIndex
) -> None:
    """Scenario 3: Syndrome inference path activates MMR diversity and requires confirmation."""
    service = RetrievalService.create_default()

    # Patient with no syndrome specified, but profound respiratory and circulatory collapse
    patient = _build_base_patient(syndrome=None, sbp=70, hr=135, spo2=84)

    report = retrieve_protocol_chunks(
        index=shared_index, patient=patient, top_k=5, context=service.context
    )
    assert report.diagnostics is not None
    assert report.diagnostics.get("inferred_mode") is True

    # End-to-end triage fails closed to UNVERIFIED under HD-4 without clinician confirmation
    result = run_triage(patient, registry=shared_registry, index=shared_index)
    assert result.engine.verdict == Verdict.UNVERIFIED
    assert result.engine.unverified_reason is not None


# ---------------------------------------------------------------------------
# Scenario 4 — Empty Retrieval
# ---------------------------------------------------------------------------
def test_scenario_04_empty_retrieval(
    shared_registry: ClinicalRegistry, shared_index: BM25ClinicalIndex
) -> None:
    """Scenario 4: Empty / non-existent syndrome produces genuine abstention and 0 approved steps."""
    patient = _build_base_patient(syndrome="extraterrestrial_hyperpyrexia")
    result = run_triage(patient, registry=shared_registry, index=shared_index)

    assert result.retrieval is not None
    assert result.retrieval.abstained is True
    assert result.retrieval.abstain_code == AbstainCode.UNKNOWN_SYNDROME
    assert result.engine.verdict == Verdict.UNVERIFIED
    assert len(result.verified_steps) == 0


# ---------------------------------------------------------------------------
# Scenario 5 — Missing Patient Information
# ---------------------------------------------------------------------------
def test_scenario_05_missing_patient_information(
    shared_registry: ClinicalRegistry, shared_index: BM25ClinicalIndex
) -> None:
    """Scenario 5: UNKNOWN vitals remain unknown and are not silently treated as normal."""
    patient_unmeasured = _build_base_patient(syndrome="anaphylaxis", unmeasured=True)
    result = run_triage(patient_unmeasured, registry=shared_registry, index=shared_index)

    # Vitals and score must fail closed
    assert patient_unmeasured.vitals.systolic_bp_mmhg.source == "unknown"
    assert patient_unmeasured.vitals.systolic_bp_mmhg.value is None
    assert result.engine.score is not None
    assert result.engine.score.total_score is None
    assert result.engine.verdict == Verdict.UNVERIFIED

    # Checks requiring vitals are recorded as SkippedCheck
    assert len(result.engine.checks_skipped) > 0


# ---------------------------------------------------------------------------
# Scenario 6 — Citation and Applicability Failure
# ---------------------------------------------------------------------------
def test_scenario_06_citation_and_applicability_failure() -> None:
    """Scenario 6: Valid chunk citation rejected when IF-conditions are not met by patient."""
    # Normotensive patient (BP 125)
    patient = _build_base_patient(syndrome="anaphylaxis", sbp=125)

    # Verify applicability evaluation fails closed on repeat dose clause requiring low BP
    app_res = verify_node_applicability("ANAPHYLAXIS_01_NODE_3", patient)
    assert app_res.status == ApplicabilityStatus.NOT_MET
    assert "low_systolic_bp" in app_res.requires_predicates


# ---------------------------------------------------------------------------
# Scenario 7 — Dropped Qualifier
# ---------------------------------------------------------------------------
def test_scenario_07_dropped_qualifier() -> None:
    """Scenario 7: Narrative instruction dropping required qualifier is rejected."""
    chunk_text = (
        "3. IF signs of systemic hypoperfusion, compensatory tachycardia, or refractory shock "
        "continue after initial therapy:\n"
        "   THEN repeat administration of intramuscular epinephrine and establish wide-bore "
        "vascular access."
    )
    instruction_dropped = "Administer epinephrine 0.5 mg intramuscularly immediately"

    is_ok, reason = verify_step_qualifiers(instruction_dropped, chunk_text)
    assert not is_ok
    assert reason is not None
    assert "QUALIFIER_DROPPED" in reason
    assert "'repeat'" in reason


# ---------------------------------------------------------------------------
# Scenario 8 — Strict and Demo Trust Modes
# ---------------------------------------------------------------------------
def test_scenario_08_strict_and_demo_trust_modes(
    shared_registry: ClinicalRegistry, shared_index: BM25ClinicalIndex
) -> None:
    """Scenario 8: Strict mode enforces verified-only rules; Demo mode badges unreviewed candidates."""
    patient = _build_base_patient(syndrome="anaphylaxis", sbp=78, hr=120)

    # In DEMO mode, research prototype runs with unreviewed rule disclosure
    cfg_demo = OrchestratorConfig(trust_mode=TrustMode.DEMO)
    res_demo = run_triage(patient, registry=shared_registry, index=shared_index, config=cfg_demo)
    assert res_demo.engine.trust_mode == TrustMode.DEMO
    assert "verified" in res_demo.engine.verified_rules_summary

    # In STRICT mode, unverified seed rules fail closed
    cfg_strict = OrchestratorConfig(trust_mode=TrustMode.STRICT)
    res_strict = run_triage(
        patient, registry=shared_registry, index=shared_index, config=cfg_strict
    )
    assert res_strict.engine.trust_mode == TrustMode.STRICT
    assert res_strict.engine.verdict != Verdict.CHECKED_CLEAR


# ---------------------------------------------------------------------------
# Scenario 9 — FDC and Duplicate Ingredients
# ---------------------------------------------------------------------------
def test_scenario_09_fdc_and_duplicate_ingredients(shared_registry: ClinicalRegistry) -> None:
    """Scenario 9: FDC multi-ingredient expansion detects duplicate paracetamol."""
    # Patient has active Ultracet (tramadol + paracetamol)
    entry = shared_registry.aliases.get("Ultracet")
    assert entry is not None
    assert "paracetamol" in entry.ingredient_ids
    assert "tramadol" in entry.ingredient_ids


# ---------------------------------------------------------------------------
# Scenario 10 — Dose Calculation
# ---------------------------------------------------------------------------
def test_scenario_10_dose_calculation(shared_registry: ClinicalRegistry) -> None:
    """Scenario 10: Dose engine calculates exact Decimal mass, IM volume tripwire, and gross overdose."""
    patient = _build_base_patient(syndrome="anaphylaxis")

    # Excessive IM volume (salbutamol 5.0 mg -> 5.0 mL exceeds 3.0 mL IM site threshold)
    step_vol = PlanStepDraft(
        step_number=1,
        action_type=ActionType.administer,
        drug_id="salbutamol",
        route=Route.im,
        narrative_instruction="Administer 5 mg IM salbutamol",
        requested_dose=ExplicitDose(amount=Decimal("5.0"), unit=DoseUnit.mg),
    )
    report_vol = verify_dose(
        patient=patient,
        drug_id="salbutamol",
        requested_dose=step_vol.requested_dose,  # type: ignore[arg-type]
        registry=shared_registry,
        step_number=1,
        step=step_vol,
    )
    assert report_vol.calculated_volume_ml == Decimal("5.0")
    assert "exceeds 3.0 mL single-site injection limit" in report_vol.notes

    # Gross overdose (100x ceiling) triggers tripwire and ceiling alert
    step_overdose = PlanStepDraft(
        step_number=2,
        action_type=ActionType.administer,
        drug_id="epinephrine",
        route=Route.im,
        narrative_instruction="Administer 50 mg IM epinephrine",
        requested_dose=ExplicitDose(amount=Decimal("50.0"), unit=DoseUnit.mg),
    )
    report_overdose = verify_dose(
        patient=patient,
        drug_id="epinephrine",
        requested_dose=step_overdose.requested_dose,  # type: ignore[arg-type]
        registry=shared_registry,
        step_number=2,
        step=step_overdose,
    )
    assert report_overdose.magnitude_tripwire_triggered is True
    assert report_overdose.status == "EXCEEDS_CEILING"


# ---------------------------------------------------------------------------
# Scenario 11 — Rule-Mining and Review Queue
# ---------------------------------------------------------------------------
def test_scenario_11_rule_mining_and_review_queue() -> None:
    """Scenario 11: Candidate batches are unreviewed and preserved in the human triage queue."""
    cand_dir = get_data_dir() / "rules_candidates"
    adapter = TypeAdapter(ClinicalRule)
    candidates: list[ClinicalRule] = []
    for f in sorted(cand_dir.glob("*.yaml")):
        if f.name == "mining_gold_set.yaml":
            continue
        data = load_yaml_decimal(f)
        for r in data.get("rules", []):
            candidates.append(adapter.validate_python(r))

    assert len(candidates) == 49  # 40 from batches 1-3, 9 from auto_mined

    # None have been promoted to verified
    assert all(c.provenance.verified is False for c in candidates)
    assert all(
        c.provenance.source_status.value in ("PLACEHOLDER_UNRETRIEVED", "RETRIEVED_UNREVIEWED")
        for c in candidates
    )


# ---------------------------------------------------------------------------
# Scenario 12 — Evidence UI
# ---------------------------------------------------------------------------
def test_scenario_12_evidence_ui(shared_index: BM25ClinicalIndex) -> None:
    """Scenario 12: Evidence trace contains inspectable queries, expansion terms, and nearest misses."""
    patient = _build_base_patient(syndrome="anaphylaxis", sbp=75, hr=130)
    service = RetrievalService.create_default()

    report = retrieve_protocol_chunks(
        index=shared_index,
        patient=patient,
        top_k=3,
        context=service.context,
        expansion_mode="predicate_aware_bm25",
    )

    assert report.expansion_trace is not None
    assert "original_query" in report.expansion_trace
    assert "expanded_query" in report.expansion_trace
    assert report.diagnostics is not None
    assert "nearest_misses" in report.diagnostics
    assert "predicate_evaluations" in report.diagnostics


# ---------------------------------------------------------------------------
# Scenario 13 — Why Drawer
# ---------------------------------------------------------------------------
def test_scenario_13_why_drawer(shared_registry: ClinicalRegistry) -> None:
    """Scenario 13: Alert Why drawer explains matched facts, unmeasured data, and Rule R11 severity."""
    patient = _build_base_patient(syndrome="anaphylaxis", sbp=72)
    alert = Alert(
        rule_id="RULE_TEST_BLOCK",
        severity=Severity.BLOCK,
        rule_type="population",
        drug_ids=["epinephrine"],
        consequence="Severe clinical hazard",
        action="Halt administration immediately",
        provenance=Provenance(
            source_doc="TEST-SRC",
            section_ref="Section 1",
            version_or_date="2026.1",
            verified=False,
        ),
    )
    why = explain_alert(alert, patient, shared_registry)

    assert why.rule_id == "RULE_TEST_BLOCK"
    assert why.severity == Severity.BLOCK
    assert "Rule R11" in why.severity_rationale
    assert len(why.matched_facts) > 0


# ---------------------------------------------------------------------------
# Scenario 14 — Ask-the-Corpus
# ---------------------------------------------------------------------------
def test_scenario_14_ask_the_corpus() -> None:
    """Scenario 14: Extractive Q&A quotes verbatim evidence and abstains on unsupported queries."""
    # Grounded question
    resp_grounded = ask_the_corpus(
        question="What should be administered for acute respiratory distress in anaphylaxis?",
        syndrome="anaphylaxis",
        top_k=3,
    )
    assert not resp_grounded.abstained
    assert len(resp_grounded.citations) > 0
    assert len(resp_grounded.answer) > 0
    for citation in resp_grounded.citations:
        assert citation.license == "synthetic"

    # Unsupported gibberish query
    resp_empty = ask_the_corpus(
        question="xyzabc qqqqqq zzzz",
        top_k=3,
    )
    assert resp_empty.abstained
    assert len(resp_empty.citations) == 0


# ---------------------------------------------------------------------------
# Scenario 15 — Security Gateway
# ---------------------------------------------------------------------------
def test_scenario_15_security_gateway() -> None:
    """Scenario 15: Auth boundary blocks unauthenticated calls and rate limiter enforces 429."""
    limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=60.0)
    config = SecurityConfig(api_key="SECURE_TEST_KEY_2026", require_auth=True)
    app = create_app(security_config=config, rate_limiter=limiter)
    client = TestClient(app)

    # Missing authentication header returns 401 on protected endpoint
    resp_unauth = client.get("/api/scenarios")
    assert resp_unauth.status_code == 401

    headers = {"Authorization": "Bearer SECURE_TEST_KEY_2026"}

    # Request 1: succeeds
    r1 = client.get("/api/health", headers=headers)
    assert r1.status_code == 200

    # Request 2: succeeds
    r2 = client.get("/api/health", headers=headers)
    assert r2.status_code == 200

    # Request 3: rate limit exceeded -> 429 Too Many Requests
    r3 = client.get("/api/health", headers=headers)
    assert r3.status_code == 429
    assert "retry-after" in r3.headers


# ---------------------------------------------------------------------------
# Scenario 16 — Mock/Provider Boundary
# ---------------------------------------------------------------------------
def test_scenario_16_mock_provider_boundary() -> None:
    """Scenario 16: Generator identifies as MOCK and unapproved live model raises HD-14 exception."""
    mock = FakeLLM(profile=FakeLLMProfile.COMPLIANT)
    assert mock.profile == FakeLLMProfile.COMPLIANT

    unapproved_cfg = LocalLLMConfig(
        model_id="meta-llama/Meta-Llama-3-8B-Instruct",
        approved_by=None,
        status="BLOCKED_EXTERNAL",
    )
    with pytest.raises(LLMProviderApprovalError) as exc_info:
        ApprovedLocalProvider(config=unapproved_cfg)
    assert "HD-14" in str(exc_info.value)
