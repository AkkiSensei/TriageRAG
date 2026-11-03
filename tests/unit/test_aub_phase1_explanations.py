"""Unit tests for AUB Phase 1 Task T1.2: Derive Explanations from Actual Execution (AUB-UX-01).

Safety Property (T1.2 / AUB-UX-01):
1. In UNVERIFIED preset (or when clinical data is incomplete/skipped), completed_checks must NOT
   falsely claim that allergy, DDI, or weight checks were completed.
2. Machine-verified step count must strictly count only APPROVED steps (excluding struck-through,
   citation-unverified, or missing-data steps).
3. Unresolved checks must accurately record skipped rules, unresolved entities, coverage gaps,
   and unverified/rejected plan steps.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from triagerag.config import get_data_dir
from triagerag.contracts.enums import (
    ActionType,
    DoseUnit,
    Route,
    StepStatus,
    Verdict,
)
from triagerag.contracts.scenarios import get_preloaded_scenario
from triagerag.contracts.schemas import (
    EngineReport,
    ExplicitDose,
    PlanStepDraft,
    ProviderMetadata,
    SpanCitation,
    VerifiedStep,
)
from triagerag.engine.registry import ClinicalRegistry
from triagerag.orchestrator import build_triage_explanation, run_triage

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)


def test_unverified_preset_completed_checks_omit_allergy_ddi_and_weight() -> None:
    """In UNVERIFIED preset, completed_checks must NOT mention allergy, DDI, or weight."""
    patient, overrides = get_preloaded_scenario("UNVERIFIED")
    data_dir = get_data_dir()
    registry = ClinicalRegistry.load_from_directory(data_dir)

    response = run_triage(patient, registry=registry, overrides=overrides)

    assert response.engine.verdict == Verdict.UNVERIFIED
    assert response.explanation is not None

    completed_str = " ".join(response.explanation.completed_checks).lower()
    assert "allergy" not in completed_str, f"Allergy found in completed_checks: {completed_str}"
    assert "drug-drug" not in completed_str, f"DDI found in completed_checks: {completed_str}"
    assert "weight" not in completed_str, f"Weight found in completed_checks: {completed_str}"

    # Unresolved checks must explicitly record the skipped checks
    unresolved_str = " ".join(response.explanation.unresolved_checks).lower()
    assert "allergy" in unresolved_str or "allergies" in unresolved_str, (
        f"Expected allergy in unresolved_checks: {unresolved_str}"
    )
    assert "medication" in unresolved_str or "medications" in unresolved_str, (
        f"Expected medication in unresolved_checks: {unresolved_str}"
    )
    assert "weight" in unresolved_str or "weight_kg" in unresolved_str, (
        f"Expected weight in unresolved_checks: {unresolved_str}"
    )


def test_machine_verified_count_excludes_struck_and_unverified_steps() -> None:
    """Machine-verified step count must only count APPROVED steps, never struck or unverified."""
    patient, _ = get_preloaded_scenario("CLEAN")

    step_approved = VerifiedStep(
        draft=PlanStepDraft(
            step_number=1,
            action_type=ActionType.administer,
            narrative_instruction="Administer epinephrine 0.3mg IM",
            drug_id="epinephrine",
            requested_dose=ExplicitDose(amount=Decimal("0.3"), unit=DoseUnit.mg),
            route=Route.im,
            citations=[
                SpanCitation(
                    chunk_id="C1",
                    doc_id="D1",
                    section="Sec1",
                    quoted_span="epinephrine IM 0.3mg",
                )
            ],
        ),
        status=StepStatus.APPROVED,
        citation_verified=True,
    )

    step_struck = VerifiedStep(
        draft=PlanStepDraft(
            step_number=2,
            action_type=ActionType.administer,
            narrative_instruction="Administer contraindicated beta-blocker",
            drug_id="metoprolol",
            requested_dose=ExplicitDose(amount=Decimal("25"), unit=DoseUnit.mg),
            route=Route.oral,
            citations=[
                SpanCitation(
                    chunk_id="C2",
                    doc_id="D2",
                    section="Sec2",
                    quoted_span="contraindicated text",
                )
            ],
        ),
        status=StepStatus.BLOCKED_STRUCK_THROUGH,
        rejection_reasons=["Severe bradycardia contraindication"],
    )

    step_unverified = VerifiedStep(
        draft=PlanStepDraft(
            step_number=3,
            action_type=ActionType.administer,
            narrative_instruction="Administer ungrounded antibiotic",
            drug_id="ceftriaxone",
            requested_dose=ExplicitDose(amount=Decimal("1000"), unit=DoseUnit.mg),
            route=Route.iv,
            citations=[
                SpanCitation(
                    chunk_id="C3",
                    doc_id="D3",
                    section="Sec3",
                    quoted_span="ungrounded span",
                )
            ],
        ),
        status=StepStatus.CITATION_UNVERIFIED,
        rejection_reasons=["Citation text not found in retrieved chunks"],
    )

    engine_report = EngineReport(
        verdict=Verdict.UNVERIFIED,
        checks_run=10,
        checks_skipped=[],
        unresolved_entities=[],
        ruleset_coverage=["ALLERGY", "DDI", "DOSE"],
        coverage_gaps=[],
        unverified_rules_evaluated=0,
    )

    # All 3 steps passed: 1 approved, 1 struck, 1 citation_unverified
    explanation = build_triage_explanation(
        engine=engine_report,
        retrieval=None,
        verified_steps=[step_approved, step_struck, step_unverified],
        patient=patient,
        provider_info=ProviderMetadata(),
        llm_fallback_mode=False,
    )

    # Machine-verified count must state 1 step, NOT 3 steps!
    machine_verified_lines = [
        line for line in explanation.completed_checks if "Machine-verified" in line
    ]
    assert len(machine_verified_lines) == 1
    assert "Machine-verified 1 proposed protocol steps" in machine_verified_lines[0]

    # Struck-through and citation unverified steps must appear in unresolved_checks
    unresolved_text = " ".join(explanation.unresolved_checks)
    assert "Proposed step 2 struck through" in unresolved_text
    assert "Proposed step 3 citation unverified" in unresolved_text


def test_all_citation_unverified_steps_yield_zero_machine_verified_in_completed() -> None:
    """When all proposed steps are CITATION_UNVERIFIED, completed_checks has no verified steps."""
    patient, _ = get_preloaded_scenario("CLEAN")

    step_unverified = VerifiedStep(
        draft=PlanStepDraft(
            step_number=1,
            action_type=ActionType.administer,
            narrative_instruction="Administer ungrounded drug",
            drug_id="aspirin",
            requested_dose=ExplicitDose(amount=Decimal("300"), unit=DoseUnit.mg),
            route=Route.oral,
            citations=[
                SpanCitation(
                    chunk_id="C1",
                    doc_id="D1",
                    section="Sec1",
                    quoted_span="unverified text",
                )
            ],
        ),
        status=StepStatus.CITATION_UNVERIFIED,
        rejection_reasons=["No supporting citation"],
    )

    engine_report = EngineReport(
        verdict=Verdict.UNVERIFIED,
        checks_run=10,
        checks_skipped=[],
        unresolved_entities=[],
        ruleset_coverage=["ALLERGY", "DDI", "DOSE"],
        coverage_gaps=[],
        unverified_rules_evaluated=0,
    )

    explanation = build_triage_explanation(
        engine=engine_report,
        retrieval=None,
        verified_steps=[step_unverified],
        patient=patient,
        provider_info=ProviderMetadata(),
        llm_fallback_mode=False,
    )

    # Must NOT have any line claiming steps were machine-verified
    assert not any("Machine-verified" in line for line in explanation.completed_checks)
    assert any(
        "Proposed step 1 citation unverified" in line for line in explanation.unresolved_checks
    )
