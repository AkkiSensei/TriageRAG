"""Unit tests for Phase 5 Task T5.1: Patient Applicability Verification.

Safety Property (AUB-GRD-01, Rule R1, Rule R2, Rule R3, Task T5.1):
1. Verifies that cited IF/THEN decision nodes are compared against patient data.
2. Anaphylaxis repeat-dose node (NODE_3, requires low_systolic_bp) returns NOT_MET
   for a patient with normal systolic blood pressure (e.g. 125 mmHg).
3. The same node returns MET for a patient with hypotension (e.g. 80 mmHg).
4. The same node returns UNKNOWN for a patient with unmeasured blood pressure.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from triagerag.contracts.schemas import Age, Measured, Patient, Vitals
from triagerag.rag.aliases import load_node_aliases
from triagerag.verify.applicability import ApplicabilityStatus, verify_node_applicability


def _create_patient(
    *,
    systolic_bp: int | None = 120,
    hr: int | None = 75,
    rr: int | None = 16,
    spo2: int | None = 98,
    temp: str | None = "36.8",
    bp_source: str = "measured",
) -> Patient:
    """Helper to build a controlled patient with explicit vitals."""
    return Patient(
        assessed_at=datetime.now(UTC),
        age=Age(value=Decimal("45"), unit="years"),
        sex="female",
        pregnancy="no",
        weight_kg=Measured[Decimal](value=Decimal("70.0"), source="measured"),
        vitals=Vitals(
            heart_rate_bpm=(
                Measured[int](value=hr, source="measured")
                if hr is not None
                else Measured[int](source="unknown")
            ),
            systolic_bp_mmhg=(
                Measured[int](value=systolic_bp, source=bp_source)
                if systolic_bp is not None
                else Measured[int](source="unknown")
            ),
            respiratory_rate_bpm=(
                Measured[int](value=rr, source="measured")
                if rr is not None
                else Measured[int](source="unknown")
            ),
            spo2_percent=(
                Measured[int](value=spo2, source="measured")
                if spo2 is not None
                else Measured[int](source="unknown")
            ),
            temperature_c=(
                Measured[Decimal](value=Decimal(temp), source="measured")
                if temp is not None
                else Measured[Decimal](source="unknown")
            ),
        ),
        medications=[],
        allergies=[],
        medication_history_status="confirmed_none",
        allergy_history_status="confirmed_nkda",
    )


class TestPatientApplicabilityVerification:
    """Tests for protocol decision node applicability against structured patient context."""

    def test_anaphylaxis_node_3_unmet_for_normal_vitals(self) -> None:
        """ANAPHYLAXIS_01_NODE_3 requires low_systolic_bp; fails for normotensive patient."""
        patient = _create_patient(systolic_bp=125)
        result = verify_node_applicability("ANAPHYLAXIS_01_NODE_3", patient)

        assert result.status == ApplicabilityStatus.NOT_MET
        assert "low_systolic_bp" in result.requires_predicates
        assert result.predicate_evaluations.get("low_systolic_bp") == "not_satisfied"
        assert "does not satisfy" in result.reason

    def test_anaphylaxis_node_3_met_for_hypotensive_patient(self) -> None:
        """ANAPHYLAXIS_01_NODE_3 passes for patient presenting with hypotension/shock."""
        patient = _create_patient(systolic_bp=82)
        result = verify_node_applicability("ANAPHYLAXIS_01_NODE_3", patient)

        assert result.status == ApplicabilityStatus.MET
        assert result.predicate_evaluations.get("low_systolic_bp") == "satisfied"
        assert "All required node predicates satisfied" in result.reason

    def test_anaphylaxis_node_3_unknown_when_bp_unmeasured(self) -> None:
        """ANAPHYLAXIS_01_NODE_3 returns UNKNOWN when systolic BP was unmeasured."""
        patient = _create_patient(systolic_bp=None, bp_source="unknown")
        result = verify_node_applicability("ANAPHYLAXIS_01_NODE_3", patient)

        assert result.status == ApplicabilityStatus.UNKNOWN
        assert result.predicate_evaluations.get("low_systolic_bp") == "unknown"
        assert "missing or unmeasured" in result.reason

    def test_anaphylaxis_node_3_resolves_via_content_addressed_id(self) -> None:
        """Content-addressed node ID resolves to same applicability declaration as legacy ID."""
        aliases = load_node_aliases()
        content_id = aliases.get("ANAPHYLAXIS_01_NODE_3")
        assert content_id is not None, "ANAPHYLAXIS_01_NODE_3 must be present in node_aliases.yaml"

        patient = _create_patient(systolic_bp=125)
        result = verify_node_applicability(content_id, patient)
        assert result.status == ApplicabilityStatus.NOT_MET
        assert result.predicate_evaluations.get("low_systolic_bp") == "not_satisfied"

    def test_parent_chunk_without_if_conditions_passes(self) -> None:
        """Parent or overview chunk without IF preconditions evaluates to MET."""
        patient = _create_patient(systolic_bp=120)
        result = verify_node_applicability("ANAPHYLAXIS_01", patient)

        assert result.status == ApplicabilityStatus.MET
        assert "Parent or non-decision chunk" in result.reason

    def test_unregistered_decision_node_fails_closed_as_unknown(self) -> None:
        """Unregistered decision node fails closed to UNKNOWN to prevent silent passes."""
        patient = _create_patient(systolic_bp=120)
        result = verify_node_applicability("UNKNOWN_PROTOCOL_NODE_99", patient)

        assert result.status == ApplicabilityStatus.UNKNOWN
        assert "no declared predicate requirements" in result.reason
