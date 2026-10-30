"""Tests for route verification and medication order hardening.

Addresses review findings in Section 8.2:
- Validate proposed administration route against drug's formulary-approved routes.
- Flag unapproved routes as FLAGGED_HIGH with actionable clinical reason.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from triagerag.config import get_data_dir
from triagerag.contracts.enums import ActionType, DoseUnit, Route, StepStatus
from triagerag.contracts.schemas import (
    Age,
    ExplicitDose,
    Measured,
    Patient,
    PlanDraft,
    PlanStepDraft,
    RetrievedChunk,
    SpanCitation,
    Vitals,
)
from triagerag.engine.registry import load_registry
from triagerag.verify.plan_verifier import verify_plan

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)


def _make_patient() -> Patient:
    return Patient(
        assessed_at=NOW,
        age=Age(value=Decimal(35), unit="years"),  # type: ignore[arg-type]
        sex="male",
        pregnancy="not_applicable",
        weight_kg=Measured[Decimal](value=Decimal("70.0"), source="measured"),
        vitals=Vitals(
            systolic_bp_mmhg=Measured[int](value=120, source="measured"),
            heart_rate_bpm=Measured[int](value=80, source="measured"),
            respiratory_rate_bpm=Measured[int](value=16, source="measured"),
            spo2_percent=Measured[int](value=98, source="measured"),
            temperature_c=Measured[Decimal](value=Decimal("37.0"), source="measured"),
        ),
        medication_history_status="confirmed_none",
        allergy_history_status="confirmed_none",
    )


def _make_chunk() -> RetrievedChunk:
    return RetrievedChunk(
        doc_id="PROTO_ANAPHYLAXIS",
        section="Immediate Management",
        chunk_id="ANAPHYLAXIS_01",
        parent_id="DOC_ANAPHYLAXIS",
        text="1. IF anaphylaxis is diagnosed: THEN administer epinephrine immediately.",
        population="adult",
        syndrome="anaphylaxis",
    )


def test_unapproved_route_flags_high() -> None:
    """An administration step with an unapproved route must be flagged FLAGGED_HIGH."""
    reg = load_registry(get_data_dir())
    patient = _make_patient()
    chunk = _make_chunk()

    # Epinephrine routes in formulary: im, iv, sc, nebulized. Oral is NOT approved.
    step = PlanStepDraft(
        step_number=1,
        action_type=ActionType.administer,
        drug_id="epinephrine",
        requested_dose=ExplicitDose(amount=Decimal("0.3"), unit=DoseUnit.mg),
        route=Route.oral,
        narrative_instruction="Administer epinephrine orally.",
        citations=[
            SpanCitation(
                doc_id="PROTO_ANAPHYLAXIS",
                section="Immediate Management",
                chunk_id="ANAPHYLAXIS_01",
                quoted_span="administer epinephrine immediately",
            )
        ],
    )
    plan = PlanDraft(matched_protocol_title="Anaphylaxis Management", steps=[step])

    verified_steps, _, _, _ = verify_plan(
        patient=patient,
        draft=plan,
        baseline_alerts=[],
        retrieved_chunks=[chunk],
        registry=reg,
    )

    assert len(verified_steps) == 1
    v_step = verified_steps[0]
    assert v_step.status == StepStatus.FLAGGED_HIGH
    assert any("not approved for 'epinephrine'" in r for r in v_step.rejection_reasons)


def test_approved_route_passes() -> None:
    """An administration step with an approved route achieves StepStatus.APPROVED."""
    reg = load_registry(get_data_dir())
    patient = _make_patient()
    chunk = _make_chunk()

    step = PlanStepDraft(
        step_number=1,
        action_type=ActionType.administer,
        drug_id="epinephrine",
        requested_dose=ExplicitDose(amount=Decimal("0.3"), unit=DoseUnit.mg),
        route=Route.im,
        narrative_instruction="Administer epinephrine IM.",
        citations=[
            SpanCitation(
                doc_id="PROTO_ANAPHYLAXIS",
                section="Immediate Management",
                chunk_id="ANAPHYLAXIS_01",
                quoted_span="administer epinephrine immediately",
            )
        ],
    )
    plan = PlanDraft(matched_protocol_title="Anaphylaxis Management", steps=[step])

    verified_steps, _, _, _ = verify_plan(
        patient=patient,
        draft=plan,
        baseline_alerts=[],
        retrieved_chunks=[chunk],
        registry=reg,
    )

    assert len(verified_steps) == 1
    v_step = verified_steps[0]
    assert v_step.status == StepStatus.APPROVED
    assert not any("not approved for 'epinephrine'" in r for r in v_step.rejection_reasons)
    assert not v_step.rejection_reasons


def test_administration_missing_route_fails_approval_as_incomplete_order() -> None:
    """An administration step without route cannot reach APPROVED (Section 4 review)."""
    reg = load_registry(get_data_dir())
    patient = _make_patient()
    chunk = _make_chunk()

    # Step has drug_id and citation, but no dose or route (incomplete protocol instruction)
    step = PlanStepDraft(
        step_number=1,
        action_type=ActionType.administer,
        drug_id="epinephrine",
        requested_dose=None,
        route=None,
        narrative_instruction="Administer epinephrine promptly as indicated.",
        citations=[
            SpanCitation(
                doc_id="PROTO_ANAPHYLAXIS",
                section="Immediate Management",
                chunk_id="ANAPHYLAXIS_01",
                quoted_span="administer epinephrine immediately",
            )
        ],
    )
    assert not step.is_complete_medication_order

    plan = PlanDraft(matched_protocol_title="Anaphylaxis Management", steps=[step])
    verified_steps, _, _, _ = verify_plan(
        patient=patient,
        draft=plan,
        baseline_alerts=[],
        retrieved_chunks=[chunk],
        registry=reg,
    )

    assert len(verified_steps) == 1
    v_step = verified_steps[0]
    assert v_step.status == StepStatus.REQUIRES_CLINICIAN_CONFIRMATION
    assert any("omits route" in r for r in v_step.rejection_reasons)
    assert any("omits explicit dose" in r for r in v_step.rejection_reasons)


def test_administration_valid_route_with_unrelated_citation_fails() -> None:
    """A valid route does not grant approval if citation is unverified (Section 4 review)."""
    reg = load_registry(get_data_dir())
    patient = _make_patient()
    # Unrelated chunk that doesn't mention epinephrine
    unrelated_chunk = RetrievedChunk(
        doc_id="PROTO_ASTHMA",
        section="Immediate Management",
        chunk_id="ASTHMA_01",
        parent_id=None,
        text="1. IF asthma exacerbation: THEN administer salbutamol immediately.",
        population="adult",
        syndrome="asthma",
    )

    step = PlanStepDraft(
        step_number=1,
        action_type=ActionType.administer,
        drug_id="epinephrine",
        requested_dose=ExplicitDose(amount=Decimal("0.3"), unit=DoseUnit.mg),
        route=Route.im,
        narrative_instruction="Administer epinephrine IM.",
        citations=[
            SpanCitation(
                doc_id="PROTO_ASTHMA",
                section="Immediate Management",
                chunk_id="ASTHMA_01",
                quoted_span="administer salbutamol immediately",
            )
        ],
    )
    plan = PlanDraft(matched_protocol_title="Anaphylaxis Management", steps=[step])
    verified_steps, _, _, _ = verify_plan(
        patient=patient,
        draft=plan,
        baseline_alerts=[],
        retrieved_chunks=[unrelated_chunk],
        registry=reg,
    )

    assert len(verified_steps) == 1
    v_step = verified_steps[0]
    assert v_step.status == StepStatus.CITATION_UNVERIFIED


def test_cumulative_daily_dose_multi_step_exceeded_flags_high() -> None:
    """Multiple administrations of epinephrine exceeding daily_max triggers HIGH alert."""
    from triagerag.engine.rule_engine import evaluate_plan

    reg = load_registry(get_data_dir())
    patient = _make_patient()

    # Adult epinephrine: per_dose_max = 0.5 mg, daily_max = 1.5 mg
    # 4 repeated doses of 0.5 mg each pass per-dose checks individually,
    # but total 2.0 mg > daily_max 1.5 mg.
    steps = [
        PlanStepDraft(
            step_number=i,
            action_type=ActionType.administer,
            drug_id="epinephrine",
            requested_dose=ExplicitDose(amount=Decimal("0.5"), unit=DoseUnit.mg),
            route=Route.im,
            narrative_instruction=f"Step {i}: Administer epinephrine 0.5mg IM.",
            citations=[
                SpanCitation(
                    doc_id="PROTO_ANAPHYLAXIS",
                    section="Immediate Management",
                    chunk_id="ANAPHYLAXIS_01",
                    quoted_span="administer epinephrine immediately",
                )
            ],
        )
        for i in range(1, 5)
    ]

    alerts, skips, dose_reports = evaluate_plan(
        patient=patient,
        steps=steps,
        baseline_alerts=[],
        registry=reg,
    )

    # Individual dose reports are OK
    assert all(d.status == "OK" for d in dose_reports)
    # But cumulative exposure triggers CUMULATIVE_DAILY_DOSE_EPINEPHRINE alert
    cum_alert = next((a for a in alerts if "CUMULATIVE_DAILY_DOSE" in a.rule_id), None)
    assert cum_alert is not None
    assert cum_alert.severity.value == "HIGH"
    assert "exceeds maximum daily limit" in cum_alert.consequence


def test_cumulative_daily_dose_prior_history_exceeded_flags_high() -> None:
    """Prior dose + proposed dose exceeding daily_max triggers HIGH alert (Section 5 review)."""
    from datetime import timedelta

    from triagerag.contracts.schemas import MedicationEntry
    from triagerag.engine.rule_engine import evaluate_plan

    reg = load_registry(get_data_dir())
    patient = _make_patient()
    # Patient confirmed to have received 1.2 mg epinephrine 2 hours ago
    prior_dose = MedicationEntry(
        raw_text="epinephrine",
        dose_taken=ExplicitDose(amount=Decimal("1.2"), unit=DoseUnit.mg),
        route=Route.im,
        last_dose_time=patient.assessed_at - timedelta(hours=2),
        resolved=True,
    )
    patient_with_history = patient.model_copy(
        update={
            "medication_history_status": "confirmed_list",
            "medications": [prior_dose],
        }
    )

    # Proposed dose 0.5 mg: 1.2 mg + 0.5 mg = 1.7 mg > 1.5 mg daily_max
    step = PlanStepDraft(
        step_number=1,
        action_type=ActionType.administer,
        drug_id="epinephrine",
        requested_dose=ExplicitDose(amount=Decimal("0.5"), unit=DoseUnit.mg),
        route=Route.im,
        narrative_instruction="Administer epinephrine 0.5mg IM.",
        citations=[
            SpanCitation(
                doc_id="PROTO_ANAPHYLAXIS",
                section="Immediate Management",
                chunk_id="ANAPHYLAXIS_01",
                quoted_span="administer epinephrine immediately",
            )
        ],
    )

    alerts, skips, _ = evaluate_plan(
        patient=patient_with_history,
        steps=[step],
        baseline_alerts=[],
        registry=reg,
    )

    cum_alert = next((a for a in alerts if "CUMULATIVE_DAILY_DOSE" in a.rule_id), None)
    assert cum_alert is not None
    assert "1.7 mg" in cum_alert.consequence
    assert "1.5 mg" in cum_alert.consequence


def test_cumulative_daily_dose_unknown_prior_history_emits_skip_and_blocks_approval() -> None:
    """Unknown prior history emits SkippedCheck and prevents step from being APPROVED (P0-B)."""
    from triagerag.contracts.schemas import PlanDraft, RetrievedChunk
    from triagerag.engine.rule_engine import evaluate_plan
    from triagerag.verify.plan_verifier import verify_plan

    reg = load_registry(get_data_dir())
    patient = _make_patient()
    # Use valid schema status: "unknown_unobtainable"
    unknown_patient = patient.model_copy(
        update={
            "medication_history_status": "unknown_unobtainable",
            "medications": [],
        }
    )

    step = PlanStepDraft(
        step_number=1,
        action_type=ActionType.administer,
        drug_id="epinephrine",
        requested_dose=ExplicitDose(amount=Decimal("0.3"), unit=DoseUnit.mg),
        route=Route.im,
        narrative_instruction="Administer first-line IM agent immediately for anaphylaxis.",
        citations=[
            SpanCitation(
                doc_id="PROTO_ANAPHYLAXIS",
                section="Immediate Management",
                chunk_id="ANAPHYLAXIS_01",
                quoted_span="administer epinephrine immediately for anaphylaxis",
            )
        ],
    )

    # 1. Direct evaluate_plan emits SkippedCheck under valid schema status
    alerts, skips, _ = evaluate_plan(
        patient=unknown_patient,
        steps=[step],
        baseline_alerts=[],
        registry=reg,
    )

    cum_skip = next((s for s in skips if "CUMULATIVE_DOSE" in s.rule_id), None)
    assert cum_skip is not None
    assert "unknown_unobtainable" in cum_skip.reason

    # 2. verify_plan propagation: step cannot receive APPROVED when cumulative dose is unverified
    retrieved_chunk = RetrievedChunk(
        chunk_id="ANAPHYLAXIS_01",
        doc_id="PROTO_ANAPHYLAXIS",
        section="Immediate Management",
        text="When anaphylaxis is recognized, administer epinephrine immediately for anaphylaxis.",
        population="adult",
        syndrome="anaphylaxis",
    )
    draft = PlanDraft(
        matched_protocol_title="Anaphylaxis Management",
        steps=[step],
    )

    v_steps, _, _, _ = verify_plan(
        patient=unknown_patient,
        draft=draft,
        baseline_alerts=[],
        retrieved_chunks=[retrieved_chunk],
        registry=reg,
    )

    assert len(v_steps) == 1
    v_step = v_steps[0]
    # Acceptance criterion: Step CANNOT receive APPROVED when cumulative check is unverified
    assert v_step.status != StepStatus.APPROVED
    assert v_step.status == StepStatus.REQUIRES_CLINICIAN_CONFIRMATION
    assert any("Cumulative daily exposure unverified" in r for r in v_step.rejection_reasons)


def test_weight_based_cumulative_dose_unit_consistency() -> None:
    """Weight-based daily dose limits are dimensionally consistent (P0-C)."""
    from triagerag.contracts.schemas import Age, AgeUnit, Measured
    from triagerag.engine.rule_engine import evaluate_plan

    reg = load_registry(get_data_dir())

    # Paediatric patient: 20 kg
    paed_patient = _make_patient().model_copy(
        update={
            "age": Age(value=Decimal("8"), unit=AgeUnit.years),
            "weight_kg": Measured[Decimal](value=Decimal("20.0"), source="measured"),
            "medication_history_status": "confirmed_none",
            "medications": [],
        }
    )

    # Paediatric epinephrine rule in formulary:
    # dose_basis: "weight", per_dose_min: 0.01, per_dose_max: 0.01, daily_max: 0.5, unit: "mg/kg"
    # For a 20 kg child, daily_max in absolute mass is 0.5 * 20 = 10.0 mg.
    # Single dose: 0.01 mg/kg * 20 kg = 0.2 mg.
    # A proposal of 2 repeated doses of 0.2 mg (total 0.4 mg) is well below the 10.0 mg daily limit.
    safe_steps = [
        PlanStepDraft(
            step_number=i,
            action_type=ActionType.administer,
            drug_id="epinephrine",
            requested_dose=ExplicitDose(amount=Decimal("0.01"), unit=DoseUnit.mg_per_kg),
            route=Route.im,
            narrative_instruction=f"Step {i}: Administer paediatric epinephrine IM.",
            citations=[
                SpanCitation(
                    doc_id="PROTO_ANAPHYLAXIS",
                    section="Immediate Management",
                    chunk_id="ANAPHYLAXIS_01",
                    quoted_span="administer epinephrine immediately",
                )
            ],
        )
        for i in range(1, 3)
    ]

    alerts, skips, _ = evaluate_plan(
        patient=paed_patient,
        steps=safe_steps,
        baseline_alerts=[],
        registry=reg,
    )
    # Total 0.4 mg is below 10.0 mg ceiling: NO cumulative dose alert should fire
    cum_alert = next((a for a in alerts if "CUMULATIVE_DAILY_DOSE" in a.rule_id), None)
    assert cum_alert is None

    # Now test an excessive dose exceeding weight-adjusted daily_max
    # (e.g. 0.3 mg/kg * 20 kg = 6 mg per dose, 2 doses = 12 mg > 10 mg daily cap)
    excessive_steps = [
        PlanStepDraft(
            step_number=i,
            action_type=ActionType.administer,
            drug_id="epinephrine",
            requested_dose=ExplicitDose(amount=Decimal("0.3"), unit=DoseUnit.mg_per_kg),
            route=Route.im,
            narrative_instruction=f"Step {i}: Administer excessive dose IM.",
            citations=[
                SpanCitation(
                    doc_id="PROTO_ANAPHYLAXIS",
                    section="Immediate Management",
                    chunk_id="ANAPHYLAXIS_01",
                    quoted_span="administer epinephrine immediately",
                )
            ],
        )
        for i in range(1, 3)
    ]

    alerts_ex, _, _ = evaluate_plan(
        patient=paed_patient,
        steps=excessive_steps,
        baseline_alerts=[],
        registry=reg,
    )
    cum_alert_ex = next((a for a in alerts_ex if "CUMULATIVE_DAILY_DOSE" in a.rule_id), None)
    assert cum_alert_ex is not None
    assert cum_alert_ex.severity.value == "HIGH"
    assert "12.00 mg" in cum_alert_ex.consequence
    assert "10.00 mg" in cum_alert_ex.consequence
