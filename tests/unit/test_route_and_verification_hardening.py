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
    """An administration step with an approved route (e.g. IM epinephrine) passes route check."""
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
    assert not any("not approved for 'epinephrine'" in r for r in v_step.rejection_reasons)

