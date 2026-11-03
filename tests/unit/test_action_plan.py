"""Tests for the deterministic action plan generator (Rule R1, R2, R11)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from triagerag.action_plan import generate_action_plan
from triagerag.contracts.enums import ActionType, AgeUnit, DoseUnit, Route, StepStatus, Verdict
from triagerag.contracts.schemas import (
    Age,
    CalculatedDoseReport,
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


def _complete_measured_response(verdict: Verdict, sbp: int = 120) -> TriageResponse:
    patient = Patient(
        assessed_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        age=Age(value=Decimal("30"), unit=AgeUnit.years),
        sex="male",
        pregnancy="not_applicable",
        weight_kg=Measured(source="measured", value=Decimal("70.0")),
        vitals=Vitals(
            heart_rate_bpm=Measured(source="measured", value=75),
            systolic_bp_mmhg=Measured(source="measured", value=sbp),
            diastolic_bp_mmhg=Measured(source="measured", value=80),
            respiratory_rate_bpm=Measured(source="measured", value=16),
            spo2_percent=Measured(source="measured", value=98),
            temperature_c=Measured(source="measured", value=Decimal("37.0")),
            gcs_total=Measured(source="measured", value=15),
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
    resp = _complete_measured_response(Verdict.CHECKED_CLEAR)
    plan = generate_action_plan(resp)
    assert len(plan.immediate_actions) > 0
    assert any("Proceed with protocol" in a.title for a in plan.immediate_actions)
    assert any(a.urgency == "routine" for a in plan.immediate_actions)


def test_action_plan_clear_with_missing_vitals_emits_unconfirmed_clearance_caution() -> None:
    """CHECKED_CLEAR with missing vitals must NEVER emit 'Proceed with protocol'; emits unconfirmed clearance caution."""
    resp = _minimal_response(Verdict.CHECKED_CLEAR)
    plan = generate_action_plan(resp)
    assert not any("Proceed with protocol" in a.title for a in plan.immediate_actions)
    caution_actions = [
        a
        for a in plan.immediate_actions
        if "Intake Incomplete: Clinical Clearance Unconfirmed" in a.title
    ]
    assert len(caution_actions) == 1
    assert caution_actions[0].urgency == "urgent"
    assert "UNCONFIRMED" in plan.decision_summary


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


def test_action_plan_unapproved_or_flagged_step_isolated_from_medications() -> None:
    """Steps that require clinician confirmation must NEVER be emitted as medication instructions."""
    resp = _minimal_response(Verdict.CHECKED_ALERTS)
    draft = PlanStepDraft(
        step_number=1,
        action_type=ActionType.administer,
        narrative_instruction="Administer IV ceftriaxone 1 g",
        drug_id="ceftriaxone",
        requested_dose=ExplicitDose(amount=Decimal("1.0"), unit=DoseUnit.g),
        route=Route.iv,
    )
    resp.verified_steps = [
        VerifiedStep(
            draft=draft,
            status=StepStatus.REQUIRES_CLINICIAN_CONFIRMATION,
            triggered_rule_ids=["ALLERGY_PCN_CEPH"],
            rejection_reasons=["Requires clinician confirmation due to penicillin allergy history"],
            citation_verified=True,
        )
    ]
    plan = generate_action_plan(resp)
    # MUST NOT be in medications
    assert len(plan.medications) == 0
    # MUST be captured in unapproved_draft_steps
    assert len(plan.unapproved_draft_steps) == 1
    assert "REQUIRES_CLINICIAN_CONFIRMATION" in plan.unapproved_draft_steps[0]
    assert "NOT approved for administration" in plan.unapproved_draft_steps[0]


def test_action_plan_unverified_citation_prohibits_medication() -> None:
    """Steps with unverified citations cannot be emitted as medication instructions."""
    resp = _minimal_response(Verdict.CHECKED_CLEAR)
    draft = PlanStepDraft(
        step_number=1,
        action_type=ActionType.administer,
        narrative_instruction="Administer unverified medication",
        drug_id="aspirin",
        requested_dose=ExplicitDose(amount=Decimal("300"), unit=DoseUnit.mg),
        route=Route.oral,
    )
    resp.verified_steps = [
        VerifiedStep(
            draft=draft,
            status=StepStatus.APPROVED,
            citation_verified=False,  # Unverified citation
        )
    ]
    plan = generate_action_plan(resp)
    assert len(plan.medications) == 0
    assert len(plan.unapproved_draft_steps) == 1
    assert "CITATION_UNVERIFIED" in plan.unapproved_draft_steps[0]


def test_confidence_distinguishes_interlock_from_case_completeness() -> None:
    """BLOCKED result with missing vitals clearly distinguishes decisive rule from incomplete case."""
    resp = _minimal_response(Verdict.BLOCKED)
    plan = generate_action_plan(resp)
    assert plan.confidence is not None
    assert plan.confidence.level == "HIGH"
    assert plan.confidence.rule_evidence == "DECISIVE_INTERLOCK"
    assert "INCOMPLETE" in plan.confidence.case_completeness
    assert any("Rule R11 Interlock" in r for r in plan.confidence.reasons)
    assert any("NOT overall clinical case completeness" in r for r in plan.confidence.reasons)


def test_action_plan_incomplete_medication_order_isolated_from_medications() -> None:
    """Draft administer steps lacking dose or route must NEVER enter medications; isolated as unapproved order."""
    resp = _complete_measured_response(Verdict.CHECKED_CLEAR)
    draft_no_dose = PlanStepDraft(
        step_number=1,
        action_type=ActionType.administer,
        narrative_instruction="Administer epinephrine promptly",
        drug_id="epinephrine",
        requested_dose=None,  # Incomplete: missing dose
        route=Route.im,
    )
    draft_neither = PlanStepDraft(
        step_number=2,
        action_type=ActionType.administer,
        narrative_instruction="Administer aspirin",
        drug_id="aspirin",
        requested_dose=None,
        route=None,  # Incomplete: missing dose and route
    )
    resp.verified_steps = [
        VerifiedStep(
            draft=draft_no_dose,
            status=StepStatus.APPROVED,
            citation_verified=True,
        ),
        VerifiedStep(
            draft=draft_neither,
            status=StepStatus.APPROVED,
            citation_verified=True,
        ),
    ]
    plan = generate_action_plan(resp)
    assert len(plan.medications) == 0
    assert len(plan.unapproved_draft_steps) == 2
    assert all("[INCOMPLETE_ORDER]" in s for s in plan.unapproved_draft_steps)
    assert any("dose" in s.lower() for s in plan.unapproved_draft_steps)
    assert any("route" in s.lower() for s in plan.unapproved_draft_steps)


def test_action_plan_dose_limit_failure_isolated_from_medications() -> None:
    """Steps that fail dose ceilings or trigger tripwires must NEVER enter medications."""
    resp = _complete_measured_response(Verdict.CHECKED_CLEAR)
    draft = PlanStepDraft(
        step_number=1,
        action_type=ActionType.administer,
        narrative_instruction="Administer epinephrine 5.0 mg IM",
        drug_id="epinephrine",
        requested_dose=ExplicitDose(amount=Decimal("5.0"), unit=DoseUnit.mg),
        route=Route.im,
    )
    resp.verified_steps = [
        VerifiedStep(
            draft=draft,
            status=StepStatus.APPROVED,
            citation_verified=True,
        )
    ]
    resp.engine = EngineReport(
        verdict=Verdict.CHECKED_CLEAR,
        checks_run=1,
        ruleset_coverage=["allergy"],
        coverage_gaps=[],
        ruleset_review_state="UNREVIEWED_DRAFT",
        dose_reports=[
            CalculatedDoseReport(
                drug_id="epinephrine",
                requested_dose=ExplicitDose(amount=Decimal("5.0"), unit=DoseUnit.mg),
                calculated_ceiling=ExplicitDose(amount=Decimal("0.5"), unit=DoseUnit.mg),
                magnitude_tripwire_triggered=True,
                status="EXCEEDS_CEILING",
                notes="Dose 5.0 mg exceeds maximum allowable ceiling of 0.5 mg; 10x magnitude warning",
                step_number=1,
            )
        ],
    )
    plan = generate_action_plan(resp)
    assert len(plan.medications) == 0
    assert len(plan.unapproved_draft_steps) == 1
    assert "[DOSE_LIMIT_FAILED]" in plan.unapproved_draft_steps[0]
    assert "EXCEEDS_CEILING" in plan.unapproved_draft_steps[0]


def test_action_plan_approved_withhold_step_excluded_from_medications() -> None:
    """Approved, citation-verified withhold step must NEVER be in medications; preserves conditions truthfully."""
    draft = PlanStepDraft(
        step_number=1,
        action_type=ActionType.withhold,
        narrative_instruction="Withhold nitroglycerin if systolic BP < 90 mmHg",
        drug_id="nitroglycerin",
    )

    # Case A: Systolic BP unmeasured -> CONDITIONAL WITHHOLD with urgency='urgent'
    resp_unmeasured = _minimal_response(Verdict.CHECKED_CLEAR)
    resp_unmeasured.verified_steps = [
        VerifiedStep(
            draft=draft,
            status=StepStatus.APPROVED,
            citation_verified=True,
            support_reason="Protocol directive to withhold nitrates in presence of hypotension risk",
        )
    ]
    plan_unmeasured = generate_action_plan(resp_unmeasured)
    assert len(plan_unmeasured.medications) == 0
    actions_unmeasured = [
        a for a in plan_unmeasured.immediate_actions if "nitroglycerin" in a.title.lower()
    ]
    assert len(actions_unmeasured) == 1
    assert (
        actions_unmeasured[0].title
        == "CONDITIONAL WITHHOLD -- nitroglycerin (if systolic BP < 90 mmHg)"
    )
    assert actions_unmeasured[0].urgency == "urgent"
    assert "threshold parameter unconfirmed" in actions_unmeasured[0].reason

    # Case B: Systolic BP measured < 90 (e.g. 85 mmHg) -> Condition met -> WITHHOLD (CONDITION MET) with urgency='immediate'
    resp_hypotensive = _complete_measured_response(Verdict.CHECKED_CLEAR, sbp=85)
    resp_hypotensive.verified_steps = [
        VerifiedStep(
            draft=draft,
            status=StepStatus.APPROVED,
            citation_verified=True,
            support_reason="Protocol directive to withhold nitrates in presence of hypotension risk",
        )
    ]
    plan_hypotensive = generate_action_plan(resp_hypotensive)
    assert len(plan_hypotensive.medications) == 0
    actions_hypo = [
        a for a in plan_hypotensive.immediate_actions if "nitroglycerin" in a.title.lower()
    ]
    assert len(actions_hypo) == 1
    assert (
        actions_hypo[0].title
        == "WITHHOLD (CONDITION MET) -- nitroglycerin (if systolic BP < 90 mmHg)"
    )
    assert actions_hypo[0].urgency == "immediate"
    assert "actively triggered" in actions_hypo[0].reason

    # Case C: Systolic BP measured >= 90 (e.g. 120 mmHg) -> Condition unmet -> CONDITIONAL WITHHOLD (Precaution) with urgency='routine'
    resp_normotensive = _complete_measured_response(Verdict.CHECKED_CLEAR, sbp=120)
    resp_normotensive.verified_steps = [
        VerifiedStep(
            draft=draft,
            status=StepStatus.APPROVED,
            citation_verified=True,
            support_reason="Protocol directive to withhold nitrates in presence of hypotension risk",
        )
    ]
    plan_normo = generate_action_plan(resp_normotensive)
    assert len(plan_normo.medications) == 0
    actions_normo = [a for a in plan_normo.immediate_actions if "nitroglycerin" in a.title.lower()]
    assert len(actions_normo) == 1
    assert (
        actions_normo[0].title
        == "CONDITIONAL WITHHOLD -- nitroglycerin (Precaution: if systolic BP < 90 mmHg)"
    )
    assert actions_normo[0].urgency == "routine"
    assert "NOT met" in actions_normo[0].reason
