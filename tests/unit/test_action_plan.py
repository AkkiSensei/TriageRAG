"""Tests for the deterministic action plan generator (Rule R1, R2, R11)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from triagerag.action_plan import generate_action_plan
from triagerag.contracts.enums import ActionType, AgeUnit, DoseUnit, Route, StepStatus, Verdict
from triagerag.contracts.schemas import (
    Age,
    EngineReport,
    ExplicitDose,
    Measured,
    Patient,
    PlanStepDraft,
    ProviderMetadata,
    TriageExplanation,
    TriageResponse,
    VerifiedStep,
    Vitals,
)


def _minimal_engine(verdict: Verdict) -> EngineReport:
    return EngineReport(
        verdict=verdict,
        checks_run=1,
        ruleset_coverage=["allergy"],
        coverage_gaps=[],
        ruleset_review_state="UNREVIEWED_DRAFT",
    )


def _minimal_response(verdict: Verdict) -> TriageResponse:
    patient = Patient(
        assessed_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        age=Age(value=Decimal("30"), unit=AgeUnit.years),
        sex="male",
        pregnancy="not_applicable",
        weight_kg=Measured(source="unknown"),
        vitals=Vitals(
            heart_rate_bpm=Measured(source="unknown"),
            systolic_bp_mmhg=Measured(source="unknown"),
        ),
        allergy_history_status="confirmed_nkda",
        medication_history_status="confirmed_none",
    )
    explanation = TriageExplanation(
        headline="Test headline",
        plain_language_summary="Test summary",
        retrieval_explanation="Test retrieval",
        evidence_summary="None",
        generation_disclosure="deterministic",
    )
    return TriageResponse(
        engine=_minimal_engine(verdict),
        explanation=explanation,
        patient=patient,
        provider_info=ProviderMetadata(),
    )


def test_action_plan_blocked_has_stop_action() -> None:
    resp = _minimal_response(Verdict.BLOCKED)
    plan = generate_action_plan(resp)
    assert plan is not None
    titles = [a.title for a in plan.immediate_actions]
    assert any("STOP" in t or "Blocked" in t for t in titles)
    assert any(a.urgency == "immediate" for a in plan.immediate_actions)


def test_action_plan_unverified_has_escalate_action() -> None:
    resp = _minimal_response(Verdict.UNVERIFIED)
    plan = generate_action_plan(resp)
    assert any(
        "Escalate" in a.title or "escalate" in a.title.lower() for a in plan.immediate_actions
    )


def test_action_plan_clear_has_proceed_action() -> None:
    resp = _minimal_response(Verdict.CHECKED_CLEAR)
    plan = generate_action_plan(resp)
    assert len(plan.immediate_actions) > 0
    assert any("Proceed" in a.title for a in plan.immediate_actions)


def test_action_plan_has_monitoring_steps() -> None:
    resp = _minimal_response(Verdict.CHECKED_CLEAR)
    plan = generate_action_plan(resp)
    assert len(plan.monitoring_steps) > 0
    assert any("Vital signs" in m.monitor for m in plan.monitoring_steps)


def test_action_plan_blocked_has_immediate_escalation() -> None:
    resp = _minimal_response(Verdict.BLOCKED)
    plan = generate_action_plan(resp)
    assert len(plan.escalation_steps) > 0
    assert any(
        "senior" in e.escalate_to.lower() or "specialist" in e.escalate_to.lower()
        for e in plan.escalation_steps
    )


def test_action_plan_decision_summary_not_empty() -> None:
    resp = _minimal_response(Verdict.CHECKED_CLEAR)
    plan = generate_action_plan(resp)
    assert len(plan.decision_summary) > 0


def test_action_plan_assumption_tags_propagated() -> None:
    resp = _minimal_response(Verdict.CHECKED_CLEAR)
    tags = ["[ASSUMED DEMO DEFAULT] Weight: 70 kg (not measured)"]
    plan = generate_action_plan(resp, assumption_tags=tags)
    assert plan.assumptions == tags
    assert "used conservative demo defaults" in plan.decision_summary


def test_action_plan_no_medications_for_blocked() -> None:
    """Blocked verdict strictly forbids recommended medications (Rule R11)."""
    resp = _minimal_response(Verdict.BLOCKED)
    # Even if verified steps had proposed medications
    draft = PlanStepDraft(
        step_number=1,
        action_type=ActionType.administer,
        narrative_instruction="Administer nitroglycerin",
        drug_id="nitroglycerin",
        requested_dose=ExplicitDose(amount=Decimal("0.4"), unit=DoseUnit.mg),
        route=Route.sublingual,
    )
    resp.verified_steps = [
        VerifiedStep(
            draft=draft,
            status=StepStatus.BLOCKED_STRUCK_THROUGH,
            triggered_rule_ids=["DDI_PDE5_NITRATE"],
            rejection_reasons=["Contraindicated with sildenafil"],
        )
    ]
    plan = generate_action_plan(resp)
    assert len(plan.medications) == 0


def test_action_plan_medications_populated_for_clear() -> None:
    """Non-blocked approved steps generate MedicationInstruction objects."""
    resp = _minimal_response(Verdict.CHECKED_CLEAR)
    draft = PlanStepDraft(
        step_number=1,
        action_type=ActionType.administer,
        narrative_instruction="Administer intramuscular epinephrine",
        drug_id="epinephrine",
        requested_dose=ExplicitDose(amount=Decimal("0.5"), unit=DoseUnit.mg),
        route=Route.im,
    )
    resp.verified_steps = [
        VerifiedStep(
            draft=draft,
            status=StepStatus.APPROVED,
            citation_verified=True,
        )
    ]
    plan = generate_action_plan(resp)
    assert len(plan.medications) == 1
    med = plan.medications[0]
    assert med.medication_name == "epinephrine"
    assert "0.5 mg" in med.dose
    assert med.route == "im"
