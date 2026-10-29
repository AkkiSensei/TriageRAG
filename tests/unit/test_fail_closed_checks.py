"""Comprehensive regression test suite for fail-closed clinical safety checks.

Safety Properties (AGENTS.md):
- Rule R1: Code decides; LLM explains.
- Rule R2: Fail closed. Missing/unknown/unresolved data -> UNVERIFIED, never clear.
- Rule R11: No override of BLOCK under any circumstances.
- Rule R12: Pure engine determinism.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import pytest

from triagerag.contracts.enums import (
    ActionType,
    AgeUnit,
    Consciousness,
    DoseUnit,
    Route,
    ScoreBand,
    StepStatus,
    Verdict,
)
from triagerag.contracts.schemas import (
    Age,
    AllergyEntry,
    ExplicitDose,
    Measured,
    MedicationEntry,
    OverrideRecord,
    Patient,
    PlanDraft,
    PlanStepDraft,
    SpanCitation,
    Vitals,
)
from triagerag.engine.verdict import resolve_verdict
from triagerag.llm.fake import FakeLLM, FakeLLMProfile
from triagerag.orchestrator import run_triage

if TYPE_CHECKING:
    from triagerag.engine.registry import ClinicalRegistry
    from triagerag.rag.index import BM25ClinicalIndex


def _build_clean_baseline_patient() -> Patient:
    """Build a baseline patient with 100% complete, verified, normal vitals and history."""
    now = datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)
    return Patient(
        assessed_at=now,
        age=Age(value=Decimal("32"), unit=AgeUnit.years),
        sex="female",
        pregnancy="no",
        weight_kg=Measured[Decimal](value=Decimal("62.0"), source="measured"),
        vitals=Vitals(
            systolic_bp_mmhg=Measured[int](value=118, source="measured"),
            diastolic_bp_mmhg=Measured[int](value=76, source="measured"),
            heart_rate_bpm=Measured[int](value=72, source="measured"),
            respiratory_rate_bpm=Measured[int](value=16, source="measured"),
            spo2_percent=Measured[int](value=98, source="measured"),
            supplemental_o2=Measured[str](value="no", source="measured"),
            temperature_c=Measured[Decimal](value=Decimal("36.8"), source="measured"),
            consciousness=Measured[Consciousness](value=Consciousness.A, source="measured"),
        ),
        allergy_history_status="confirmed_none",
        allergies=[],
        medication_history_status="confirmed_none",
        medications=[],
        renal_impairment="no",
        hepatic_impairment="no",
        suspected_syndrome="anaphylaxis",
        chief_complaint_untrusted="Allergic reaction symptoms after wasp sting",
    )


def test_missing_vitals_fails_closed_to_unverified(
    clinical_registry: ClinicalRegistry,
    bm25_index: BM25ClinicalIndex,
) -> None:
    """Missing or unmeasured vital signs must force ScoreBand.UNSCORED and Verdict.UNVERIFIED."""
    patient = _build_clean_baseline_patient()
    # Remove required vital signs
    patient.vitals = Vitals(
        systolic_bp_mmhg=Measured[int](),
        heart_rate_bpm=Measured[int](),
        respiratory_rate_bpm=Measured[int](),
        spo2_percent=Measured[int](),
    )

    response = run_triage(
        patient=patient,
        registry=clinical_registry,
        index=bm25_index,
        llm=None,
    )

    assert response.engine.score is not None
    assert response.engine.score.band == ScoreBand.UNSCORED
    assert len(response.engine.score.missing_vitals) > 0

    # Rule R2: Missing vitals must NEVER produce CHECKED_CLEAR
    assert response.engine.verdict == Verdict.UNVERIFIED
    assert response.engine.verdict != Verdict.CHECKED_CLEAR

    # Transparent reporting: SkippedCheck must be present in checks_skipped
    assert len(response.engine.checks_skipped) > 0
    scoring_skips = [
        s for s in response.engine.checks_skipped if s.rule_type == "physiological_scoring"
    ]
    assert len(scoring_skips) > 0
    assert any("heart_rate_bpm" in s.missing_fields for s in scoring_skips)


def test_unknown_medication_history_fails_closed(
    clinical_registry: ClinicalRegistry,
    bm25_index: BM25ClinicalIndex,
) -> None:
    """Unknown or unobtainable medication history must force Verdict.UNVERIFIED."""
    patient = _build_clean_baseline_patient()
    patient.medication_history_status = "unknown_unobtainable"

    response = run_triage(
        patient=patient,
        registry=clinical_registry,
        index=bm25_index,
        llm=None,
    )

    # Rule R2: Unknown medication history must NEVER produce CHECKED_CLEAR
    assert response.engine.verdict == Verdict.UNVERIFIED
    assert response.engine.verdict != Verdict.CHECKED_CLEAR

    med_skips = [s for s in response.engine.checks_skipped if "medications" in s.missing_fields]
    assert len(med_skips) > 0


def test_incomplete_medication_history_fails_closed(
    clinical_registry: ClinicalRegistry,
    bm25_index: BM25ClinicalIndex,
) -> None:
    """Incomplete medication history must force Verdict.UNVERIFIED."""
    patient = _build_clean_baseline_patient()
    patient.medication_history_status = "incomplete"

    response = run_triage(
        patient=patient,
        registry=clinical_registry,
        index=bm25_index,
        llm=None,
    )

    assert response.engine.verdict == Verdict.UNVERIFIED
    med_skips = [s for s in response.engine.checks_skipped if "medications" in s.missing_fields]
    assert len(med_skips) > 0


def test_unknown_allergy_history_fails_closed(
    clinical_registry: ClinicalRegistry,
    bm25_index: BM25ClinicalIndex,
) -> None:
    """Unknown or unobtainable allergy history must force Verdict.UNVERIFIED."""
    patient = _build_clean_baseline_patient()
    patient.allergy_history_status = "unknown_unobtainable"

    response = run_triage(
        patient=patient,
        registry=clinical_registry,
        index=bm25_index,
        llm=None,
    )

    assert response.engine.verdict == Verdict.UNVERIFIED
    assert response.engine.verdict != Verdict.CHECKED_CLEAR

    allergy_skips = [s for s in response.engine.checks_skipped if "allergies" in s.missing_fields]
    assert len(allergy_skips) > 0


def test_unknown_allergy_reaction_type_fails_closed(
    clinical_registry: ClinicalRegistry,
    bm25_index: BM25ClinicalIndex,
) -> None:
    """Documented allergy with reaction_type='unknown' must fail closed to Verdict.UNVERIFIED."""
    patient = _build_clean_baseline_patient()
    patient.allergy_history_status = "confirmed_list"
    patient.allergies = [
        AllergyEntry(
            raw_substance="penicillin",
            reaction_type="unknown",
            resolved=True,
        )
    ]

    response = run_triage(
        patient=patient,
        registry=clinical_registry,
        index=bm25_index,
        llm=None,
    )

    assert response.engine.verdict == Verdict.UNVERIFIED
    rxn_skips = [s for s in response.engine.checks_skipped if "reaction_type" in s.missing_fields]
    assert len(rxn_skips) > 0


def test_unresolved_medication_entity_fails_closed(
    clinical_registry: ClinicalRegistry,
    bm25_index: BM25ClinicalIndex,
) -> None:
    """Unresolved home medication brand/substance must fail closed to Verdict.UNVERIFIED."""
    patient = _build_clean_baseline_patient()
    patient.medication_history_status = "confirmed_list"
    patient.medications = [
        MedicationEntry(
            raw_text="ExoticHerbalExtract_X",
            resolved=False,
            ingredients=[],
        )
    ]

    response = run_triage(
        patient=patient,
        registry=clinical_registry,
        index=bm25_index,
        llm=None,
    )

    assert response.engine.verdict == Verdict.UNVERIFIED
    assert "ExoticHerbalExtract_X" in response.engine.unresolved_entities
    unresolved_skips = [
        s for s in response.engine.checks_skipped if "medications_resolved" in s.missing_fields
    ]
    assert len(unresolved_skips) > 0


def test_unresolved_allergen_entity_fails_closed(
    clinical_registry: ClinicalRegistry,
    bm25_index: BM25ClinicalIndex,
) -> None:
    """Unresolved allergen substance must fail closed to Verdict.UNVERIFIED."""
    patient = _build_clean_baseline_patient()
    patient.allergy_history_status = "confirmed_list"
    patient.allergies = [
        AllergyEntry(
            raw_substance="MysteriousChemicalCompound_Z",
            reaction_type="mild_rash",
            resolved=False,
        )
    ]

    response = run_triage(
        patient=patient,
        registry=clinical_registry,
        index=bm25_index,
        llm=None,
    )

    assert response.engine.verdict == Verdict.UNVERIFIED
    assert "MysteriousChemicalCompound_Z" in response.engine.unresolved_entities


def test_rule_coverage_gap_renal_impairment_fails_closed(
    clinical_registry: ClinicalRegistry,
    bm25_index: BM25ClinicalIndex,
) -> None:
    """Documented renal impairment without renal dosing rules must emit a coverage gap skip."""
    patient = _build_clean_baseline_patient()
    patient.renal_impairment = "yes"

    response = run_triage(
        patient=patient,
        registry=clinical_registry,
        index=bm25_index,
        llm=None,
    )

    assert response.engine.verdict == Verdict.UNVERIFIED
    assert response.engine.verdict != Verdict.CHECKED_CLEAR
    gap_skips = [s for s in response.engine.checks_skipped if s.rule_type == "coverage_gap"]
    assert len(gap_skips) > 0
    assert any("renal" in s.rule_id.lower() for s in gap_skips)


def test_rule_coverage_gap_hepatic_impairment_fails_closed(
    clinical_registry: ClinicalRegistry,
    bm25_index: BM25ClinicalIndex,
) -> None:
    """Documented hepatic impairment without hepatic dosing rules must emit a coverage gap skip."""
    patient = _build_clean_baseline_patient()
    patient.hepatic_impairment = "yes"

    response = run_triage(
        patient=patient,
        registry=clinical_registry,
        index=bm25_index,
        llm=None,
    )

    assert response.engine.verdict == Verdict.UNVERIFIED
    gap_skips = [s for s in response.engine.checks_skipped if s.rule_type == "coverage_gap"]
    assert len(gap_skips) > 0
    assert any("hepatic" in s.rule_id.lower() for s in gap_skips)


def test_ungrounded_plan_citation_forces_unverified_verdict(
    clinical_registry: ClinicalRegistry,
    bm25_index: BM25ClinicalIndex,
) -> None:
    """Ungrounded citations must receive CITATION_UNVERIFIED and lattice UNVERIFIED."""
    patient = _build_clean_baseline_patient()
    llm = FakeLLM(FakeLLMProfile.INVALID_CITATION)

    response = run_triage(
        patient=patient,
        registry=clinical_registry,
        index=bm25_index,
        llm=llm,
    )

    assert len(response.verified_steps) > 0
    first_step = response.verified_steps[0]
    # Step must not be approved
    assert first_step.status in (StepStatus.CITATION_UNVERIFIED, StepStatus.BLOCKED_STRUCK_THROUGH)
    assert response.engine.verdict == Verdict.UNVERIFIED


def test_missing_dose_weight_forces_unverified_verdict(
    clinical_registry: ClinicalRegistry,
    bm25_index: BM25ClinicalIndex,
) -> None:
    """When weight is unknown for weight-based dosing, step status is UNVERIFIED_MISSING_DATA."""
    now = datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)
    patient = Patient(
        assessed_at=now,
        age=Age(value=Decimal("6"), unit=AgeUnit.years),
        sex="male",
        pregnancy="no",
        weight_kg=Measured[Decimal](value=None, source="unknown"),
        vitals=Vitals(
            systolic_bp_mmhg=Measured[int](value=100, source="measured"),
            heart_rate_bpm=Measured[int](value=95, source="measured"),
            respiratory_rate_bpm=Measured[int](value=22, source="measured"),
            spo2_percent=Measured[int](value=97, source="measured"),
            supplemental_o2=Measured[str](value="no", source="measured"),
            temperature_c=Measured[Decimal](value=Decimal("37.0"), source="measured"),
            consciousness=Measured[Consciousness](value=Consciousness.A, source="measured"),
        ),
        allergy_history_status="confirmed_none",
        allergies=[],
        medication_history_status="confirmed_none",
        medications=[],
        renal_impairment="no",
        hepatic_impairment="no",
        suspected_syndrome="anaphylaxis",
        chief_complaint_untrusted="Pediatric allergic reaction",
    )

    llm = FakeLLM(FakeLLMProfile.COMPLIANT)
    response = run_triage(
        patient=patient,
        registry=clinical_registry,
        index=bm25_index,
        llm=llm,
    )

    assert response.engine.verdict == Verdict.UNVERIFIED
    # Weight check must be recorded as skipped check
    weight_skips = [s for s in response.engine.checks_skipped if "weight_kg" in s.missing_fields]
    assert len(weight_skips) > 0


def test_block_alerts_force_blocked_verdict_and_cannot_override(
    clinical_registry: ClinicalRegistry,
    bm25_index: BM25ClinicalIndex,
) -> None:
    """Contraindication BLOCK alert strikes step, sets BLOCKED verdict, and forbids override."""
    now = datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)
    # Anaphylaxis allergy to penicillin
    patient = Patient(
        assessed_at=now,
        age=Age(value=Decimal("40"), unit=AgeUnit.years),
        sex="male",
        pregnancy="no",
        weight_kg=Measured[Decimal](value=Decimal("75.0"), source="measured"),
        vitals=Vitals(
            systolic_bp_mmhg=Measured[int](value=120, source="measured"),
            heart_rate_bpm=Measured[int](value=80, source="measured"),
            respiratory_rate_bpm=Measured[int](value=18, source="measured"),
            spo2_percent=Measured[int](value=99, source="measured"),
            supplemental_o2=Measured[str](value="no", source="measured"),
            temperature_c=Measured[Decimal](value=Decimal("37.0"), source="measured"),
            consciousness=Measured[Consciousness](value=Consciousness.A, source="measured"),
        ),
        allergy_history_status="confirmed_list",
        allergies=[
            AllergyEntry(
                raw_substance="amoxicillin",
                reaction_type="anaphylaxis_ige",
                resolved=True,
            )
        ],
        medication_history_status="confirmed_none",
        medications=[],
        renal_impairment="no",
        hepatic_impairment="no",
        suspected_syndrome="chest_pain",
    )

    draft = PlanDraft(
        matched_protocol_title="Infection Protocol",
        steps=[
            PlanStepDraft(
                step_number=1,
                action_type=ActionType.administer,
                drug_id="cephalexin",
                narrative_instruction="Administer cephalexin orally",
                route=Route.oral,
                requested_dose=ExplicitDose(amount=Decimal("500"), unit=DoseUnit.mg),
                citations=[
                    SpanCitation(
                        doc_id="EMERG_INFECTION",
                        section="Infection Protocol",
                        chunk_id="INFECT_01_NODE_1",
                        quoted_span="administer cephalexin orally",
                    )
                ],
            )
        ],
    )

    # Mock llm returning this draft
    class DraftMockLLM:
        def draft_plan(self, ctx: Any) -> PlanDraft:
            return draft

    # Run triage with this draft
    response = run_triage(
        patient=patient,
        registry=clinical_registry,
        index=bm25_index,
        llm=DraftMockLLM(),  # type: ignore[arg-type]
    )

    # 1. Step must be struck through
    assert response.verified_steps[0].status == StepStatus.BLOCKED_STRUCK_THROUGH
    # 2. Overall engine verdict must be BLOCKED
    assert response.engine.verdict == Verdict.BLOCKED

    # 3. Clinician override must be rejected with PermissionError (Rule R11)
    override = OverrideRecord(
        rule_id="ALLERGY_PENICILLIN_CEPH_R1_SIMILAR",
        step_number=1,
        reason="Clinician attempting override of contraindicated beta-lactam",
        clinician_id="DOC_ATTENDING",
    )
    with pytest.raises(PermissionError, match="Rule R11 Violation"):
        run_triage(
            patient=patient,
            registry=clinical_registry,
            index=bm25_index,
            llm=DraftMockLLM(),  # type: ignore[arg-type]
            overrides=[override],
        )


def test_verdict_lattice_order_comprehensive() -> None:
    """Assert 4-level lattice order: BLOCKED > UNVERIFIED > CHECKED_ALERTS > CHECKED_CLEAR."""
    # Priority 1: BLOCKED wins over everything
    assert (
        resolve_verdict(
            has_block=True,
            has_skip_or_unresolved=True,
            has_alert=True,
            has_unverified_steps=True,
        )
        == Verdict.BLOCKED
    )
    assert (
        resolve_verdict(
            has_block=True,
            has_skip_or_unresolved=False,
            has_alert=False,
        )
        == Verdict.BLOCKED
    )

    # Priority 2: UNVERIFIED wins over CHECKED_ALERTS and CHECKED_CLEAR
    assert (
        resolve_verdict(
            has_block=False,
            has_skip_or_unresolved=True,
            has_alert=True,
        )
        == Verdict.UNVERIFIED
    )
    assert (
        resolve_verdict(
            has_block=False,
            has_skip_or_unresolved=False,
            has_alert=True,
            has_unverified_steps=True,
        )
        == Verdict.UNVERIFIED
    )
    assert (
        resolve_verdict(
            has_block=False,
            has_skip_or_unresolved=False,
            has_alert=False,
            has_coverage_gaps=True,
        )
        == Verdict.UNVERIFIED
    )

    # Priority 3: CHECKED_ALERTS wins over CHECKED_CLEAR
    assert (
        resolve_verdict(
            has_block=False,
            has_skip_or_unresolved=False,
            has_alert=True,
        )
        == Verdict.CHECKED_ALERTS
    )

    # Priority 4: CHECKED_CLEAR only when completely clean
    assert (
        resolve_verdict(
            has_block=False,
            has_skip_or_unresolved=False,
            has_alert=False,
            has_unverified_steps=False,
            has_coverage_gaps=False,
        )
        == Verdict.CHECKED_CLEAR
    )
