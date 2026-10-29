"""Tests for hard BLOCK rule check and citation grounding verification.

Verifies:
1. Hard BLOCK severity alerts are enforced across allergy cross-reactivity,
   class interactions, and population/vitals rules (no unsafe recommendations pass).
2. Overall verdict enforces BLOCK > UNVERIFIED > CHECKED_ALERTS > CHECKED_CLEAR.
3. No override path exists for any BLOCK rule or blocked step under any condition.
4. Parent-only chunk citations are rejected even when only the parent chunk is retrieved.
5. Verbatim quoted span matching rejects altered casing and non-verbatim spans.
6. Failures are marked as CITATION_UNVERIFIED or BLOCKED_STRUCK_THROUGH, never APPROVED.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from triagerag.config import get_data_dir
from triagerag.contracts.enums import (
    ActionType,
    AgeUnit,
    DoseUnit,
    Route,
    StepStatus,
    Verdict,
)
from triagerag.contracts.schemas import (
    Age,
    AllergyEntry,
    ExplicitDose,
    IngredientStrength,
    Measured,
    MedicationEntry,
    OverrideRecord,
    Patient,
    PlanDraft,
    PlanStepDraft,
    RetrievedChunk,
    SpanCitation,
    Vitals,
)
from triagerag.engine.registry import ClinicalRegistry
from triagerag.orchestrator import run_triage
from triagerag.rag.index import BM25ClinicalIndex
from triagerag.rag.ingest import ingest_protocols
from triagerag.verify.citations import verify_citation
from triagerag.verify.plan_verifier import verify_plan


@pytest.fixture
def clinical_fixtures() -> tuple[ClinicalRegistry, BM25ClinicalIndex]:
    data_dir = get_data_dir()
    registry = ClinicalRegistry.load_from_directory(data_dir)
    chunks = ingest_protocols(data_dir)
    index = BM25ClinicalIndex(chunks)
    return registry, index


def test_allergy_crossreactivity_block_enforced_on_plan_step(
    clinical_fixtures: tuple[ClinicalRegistry, BM25ClinicalIndex],
) -> None:
    """BLOCK rule ALLERGY_BETALACTAM_SCAR_CATCHALL must strike through ceftriaxone."""
    registry, index = clinical_fixtures
    now = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)

    patient = Patient(
        assessed_at=now,
        age=Age(value=Decimal("40"), unit=AgeUnit.years),
        sex="female",
        pregnancy="no",
        weight_kg=Measured[Decimal](value=Decimal("65.0"), source="measured"),
        vitals=Vitals(
            heart_rate_bpm=Measured[int](value=80, source="measured"),
            systolic_bp_mmhg=Measured[int](value=120, source="measured"),
        ),
        medication_history_status="confirmed_none",
        allergy_history_status="confirmed_list",
        allergies=[
            AllergyEntry(
                raw_substance="penicillin",
                normalized_allergen_id="penicillin",
                allergen_class="BETA_LACTAMS",
                reaction_type="severe_cutaneous_scar",
                resolved=True,
            )
        ],
        suspected_syndrome="paed_sepsis",  # sepsis protocol has antibiotic nodes
    )

    chunk = RetrievedChunk(
        doc_id="EMERG_PAED_SEPSIS",
        section="Paediatric Resuscitation",
        chunk_id="PAED_SEPSIS_01_NODE_1",
        parent_id="PAED_SEPSIS_01",
        text="1. IF severe infection is suspected:\n   THEN administer ceftriaxone promptly.",
        population="adult",
        syndrome="paed_sepsis",
    )

    draft = PlanDraft(
        matched_protocol_title="Paediatric Resuscitation",
        steps=[
            PlanStepDraft(
                step_number=1,
                action_type=ActionType.administer,
                narrative_instruction="Administer ceftriaxone promptly for suspected infection",
                drug_id="ceftriaxone",
                requested_dose=ExplicitDose(amount=Decimal("1000"), unit=DoseUnit.mg),
                route=Route.iv,
                citations=[
                    SpanCitation(
                        doc_id="EMERG_PAED_SEPSIS",
                        section="Paediatric Resuscitation",
                        chunk_id="PAED_SEPSIS_01_NODE_1",
                        quoted_span="THEN administer ceftriaxone promptly.",
                    )
                ],
            )
        ],
    )

    v_steps, plan_alerts, skips, _ = verify_plan(
        patient=patient,
        draft=draft,
        baseline_alerts=[],
        retrieved_chunks=[chunk],
        registry=registry,
    )

    # Ceftriaxone step MUST be BLOCKED_STRUCK_THROUGH due to penicillin SCAR history
    assert v_steps[0].status == StepStatus.BLOCKED_STRUCK_THROUGH
    assert any("ALLERGY_BETALACTAM_SCAR_CATCHALL" in r for r in v_steps[0].triggered_rule_ids)


def test_ddi_class_interaction_block_enforced_on_plan_step(
    clinical_fixtures: tuple[ClinicalRegistry, BM25ClinicalIndex],
) -> None:
    """BLOCK rule DDI_PDE5_NITRATE strikes nitroglycerin when sildenafil recently taken."""
    registry, index = clinical_fixtures
    now = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)

    patient = Patient(
        assessed_at=now,
        age=Age(value=Decimal("58"), unit=AgeUnit.years),
        sex="male",
        pregnancy="not_applicable",
        weight_kg=Measured[Decimal](value=Decimal("80.0"), source="measured"),
        vitals=Vitals(
            heart_rate_bpm=Measured[int](value=75, source="measured"),
            systolic_bp_mmhg=Measured[int](value=130, source="measured"),
        ),
        medication_history_status="confirmed_list",
        medications=[
            MedicationEntry(
                raw_text="sildenafil",
                resolved=True,
                ingredients=[IngredientStrength(ingredient_id="sildenafil")],
                last_dose_time=now - timedelta(hours=6),
            )
        ],
        allergy_history_status="confirmed_none",
        suspected_syndrome="chest_pain",
    )

    chunk = RetrievedChunk(
        doc_id="EMERG_CHEST_PAIN",
        section="Acute Coronary Syndromes Screening",
        chunk_id="CHEST_PAIN_01_NODE_2",
        parent_id="CHEST_PAIN_01",
        text=(
            "2. IF acute ischemic chest pain is ongoing:\n"
            "   THEN administer nitroglycerin sublingually."
        ),
        population="adult",
        syndrome="chest_pain",
    )

    draft = PlanDraft(
        matched_protocol_title="Acute Coronary Syndromes Screening",
        steps=[
            PlanStepDraft(
                step_number=1,
                action_type=ActionType.administer,
                narrative_instruction="Administer nitroglycerin sublingually for chest pain",
                drug_id="nitroglycerin",
                requested_dose=ExplicitDose(amount=Decimal("0.4"), unit=DoseUnit.mg),
                route=Route.sublingual,
                citations=[
                    SpanCitation(
                        doc_id="EMERG_CHEST_PAIN",
                        section="Acute Coronary Syndromes Screening",
                        chunk_id="CHEST_PAIN_01_NODE_2",
                        quoted_span="THEN administer nitroglycerin sublingually.",
                    )
                ],
            )
        ],
    )

    v_steps, plan_alerts, _, _ = verify_plan(
        patient=patient,
        draft=draft,
        baseline_alerts=[],
        retrieved_chunks=[chunk],
        registry=registry,
    )

    # Nitroglycerin step MUST be BLOCKED_STRUCK_THROUGH due to concurrent PDE5 inhibitor
    assert v_steps[0].status == StepStatus.BLOCKED_STRUCK_THROUGH
    assert any("DDI_PDE5_NITRATE" in r for r in v_steps[0].triggered_rule_ids)


def test_invented_drug_verdict_is_blocked(
    clinical_fixtures: tuple[ClinicalRegistry, BM25ClinicalIndex],
) -> None:
    """When a plan contains an unapproved or struck drug, overall engine verdict MUST be BLOCKED."""
    from tests.integration.test_orchestrator import _build_anaphylaxis_patient
    from triagerag.llm.fake import FakeLLM, FakeLLMProfile

    registry, index = clinical_fixtures
    patient = _build_anaphylaxis_patient()
    llm = FakeLLM(FakeLLMProfile.INVENT_DRUG)

    response = run_triage(patient, registry=registry, llm=llm, index=index)
    assert response.verified_steps[0].status == StepStatus.BLOCKED_STRUCK_THROUGH
    assert response.engine.verdict == Verdict.BLOCKED


def test_parent_only_citation_rejected_even_without_child_in_retrieved(
    clinical_fixtures: tuple[ClinicalRegistry, BM25ClinicalIndex],
) -> None:
    """Citation quoting parent chunk must be rejected even if only parent is passed."""
    parent_chunk = RetrievedChunk(
        doc_id="EMERG_CHEST_PAIN",
        section="Acute Coronary Syndromes Screening",
        chunk_id="CHEST_PAIN_01",
        parent_id=None,
        text=(
            "1. IF the adult patient reports acute ischemic chest discomfort:\n"
            "   THEN obtain immediate 12-lead electrocardiogram and attach "
            "continuous cardiac monitor."
        ),
        population="adult",
        syndrome="chest_pain",
    )

    cit = SpanCitation(
        doc_id="EMERG_CHEST_PAIN",
        section="Acute Coronary Syndromes Screening",
        chunk_id="CHEST_PAIN_01",
        quoted_span="obtain immediate 12-lead electrocardiogram",
    )

    # Only parent_chunk in retrieved_chunks
    is_valid, _, reason = verify_citation(
        citation=cit,
        retrieved_chunks=[parent_chunk],
        narrative_instruction="Obtain immediate 12-lead electrocardiogram",
    )
    assert is_valid is False
    assert reason is not None
    assert "Parent-only citation" in reason


def test_non_verbatim_casing_citation_rejected(
    clinical_fixtures: tuple[ClinicalRegistry, BM25ClinicalIndex],
) -> None:
    """Quoted span with altered non-verbatim casing must fail exact substring matching."""
    chunk = RetrievedChunk(
        doc_id="EMERG_CHEST_PAIN",
        section="Acute Coronary Syndromes Screening",
        chunk_id="CHEST_PAIN_01_NODE_1",
        parent_id="CHEST_PAIN_01",
        text=(
            "1. IF the adult patient reports acute ischemic chest discomfort:\n"
            "   THEN obtain immediate 12-lead electrocardiogram and attach "
            "continuous cardiac monitor."
        ),
        population="adult",
        syndrome="chest_pain",
    )

    # Casing altered to ALL UPPERCASE -> Not verbatim substring
    cit = SpanCitation(
        doc_id="EMERG_CHEST_PAIN",
        section="Acute Coronary Syndromes Screening",
        chunk_id="CHEST_PAIN_01_NODE_1",
        quoted_span="OBTAIN IMMEDIATE 12-LEAD ELECTROCARDIOGRAM",
    )

    is_valid, _, reason = verify_citation(
        citation=cit,
        retrieved_chunks=[chunk],
        narrative_instruction="Obtain immediate 12-lead electrocardiogram",
    )
    assert is_valid is False
    assert reason is not None
    assert "not a verbatim substring" in reason


def test_no_override_path_for_block_rule_id(
    clinical_fixtures: tuple[ClinicalRegistry, BM25ClinicalIndex],
) -> None:
    """Attempting to override a rule with BLOCK severity raises PermissionError."""
    from tests.integration.test_orchestrator import _build_anaphylaxis_patient
    from triagerag.llm.fake import FakeLLM, FakeLLMProfile

    registry, index = clinical_fixtures
    patient = _build_anaphylaxis_patient()
    llm = FakeLLM(FakeLLMProfile.COMPLIANT)

    # Attempt to override a BLOCK severity rule (e.g. ALLERGY_BETALACTAM_SCAR_CATCHALL)
    override = OverrideRecord(
        rule_id="ALLERGY_BETALACTAM_SCAR_CATCHALL",
        step_number=1,
        reason="Attempting clinician override of a BLOCK severity contraindication rule",
        clinician_id="DOC_999",
    )

    with pytest.raises(PermissionError) as exc_info:
        run_triage(patient, registry=registry, llm=llm, index=index, overrides=[override])

    assert "Rule R11 Violation" in str(exc_info.value)
    assert "BLOCK" in str(exc_info.value)


def test_verdict_lattice_order_block_over_unverified() -> None:
    """Ensure system enforces BLOCK > UNVERIFIED > CHECKED_ALERTS > CHECKED_CLEAR."""
    from triagerag.engine.verdict import resolve_verdict

    # BLOCK beats UNVERIFIED
    assert (
        resolve_verdict(has_block=True, has_skip_or_unresolved=True, has_alert=True)
        == Verdict.BLOCKED
    )
    # UNVERIFIED beats CHECKED_ALERTS
    assert (
        resolve_verdict(has_block=False, has_skip_or_unresolved=True, has_alert=True)
        == Verdict.UNVERIFIED
    )
    # CHECKED_ALERTS beats CHECKED_CLEAR
    assert (
        resolve_verdict(has_block=False, has_skip_or_unresolved=False, has_alert=True)
        == Verdict.CHECKED_ALERTS
    )
    # No issues -> CHECKED_CLEAR
    assert (
        resolve_verdict(has_block=False, has_skip_or_unresolved=False, has_alert=False)
        == Verdict.CHECKED_CLEAR
    )
