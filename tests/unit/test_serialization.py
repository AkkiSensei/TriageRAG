"""Serialization round-trip tests for TriageResponse, Patient, and clinical numerics.

Safety Properties (Rule R8, R12):
1. Exact Decimal preservation across JSON serialization (never float; 84.7, 0.1+0.2 preserved).
2. Timezone-aware datetimes preserve ISO-8601 format and UTC offset.
3. Enums round-trip to identical enum types.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from triagerag.config import get_data_dir
from triagerag.contracts.enums import (
    AgeUnit,
    Consciousness,
    DoseUnit,
)
from triagerag.contracts.schemas import (
    Age,
    ExplicitDose,
    IngredientStrength,
    Measured,
    MedicationEntry,
    Patient,
    TriageResponse,
    Vitals,
)
from triagerag.engine.registry import ClinicalRegistry
from triagerag.llm.fake import FakeLLM, FakeLLMProfile
from triagerag.orchestrator import run_triage
from triagerag.rag.index import BM25ClinicalIndex
from triagerag.rag.ingest import ingest_protocols


def test_decimal_numeric_exact_preservation() -> None:
    """Rule R8: Decimals like 84.7 and 0.1+0.2 must not suffer float rounding artifacts."""
    val_84_7 = Decimal("84.7")
    val_sum = Decimal("0.1") + Decimal("0.2")  # Exact Decimal("0.3")
    dose = ExplicitDose(amount=val_84_7, unit=DoseUnit.mg)

    json_str = dose.model_dump_json()
    assert "84.7" in json_str

    # Deserialization check
    round_trip = ExplicitDose.model_validate_json(json_str)
    assert round_trip.amount == val_84_7
    assert str(round_trip.amount) == "84.7"

    dose_sum = ExplicitDose(amount=val_sum, unit=DoseUnit.mg)
    json_sum = dose_sum.model_dump_json()
    assert "0.3" in json_sum
    assert "0.30000000000000004" not in json_sum

    round_trip_sum = ExplicitDose.model_validate_json(json_sum)
    assert round_trip_sum.amount == Decimal("0.3")


def test_patient_serialization_round_trip() -> None:
    """Patient schema round-trips through JSON preserving all Decimals, datetimes, and Enums."""
    now = datetime(2026, 10, 26, 12, 34, 56, tzinfo=UTC)
    patient = Patient(
        assessed_at=now,
        age=Age(value=Decimal("84.7"), unit=AgeUnit.years),
        sex="female",
        pregnancy="no",
        weight_kg=Measured[Decimal](value=Decimal("62.35"), source="measured"),
        vitals=Vitals(
            systolic_bp_mmhg=Measured[int](value=128, source="measured"),
            heart_rate_bpm=Measured[int](value=76, source="measured"),
            respiratory_rate_bpm=Measured[int](value=16, source="measured"),
            spo2_percent=Measured[int](value=98, source="measured"),
            supplemental_o2=Measured[str](value="no", source="measured"),  # type: ignore[arg-type]
            temperature_c=Measured[Decimal](value=Decimal("36.75"), source="measured"),
            consciousness=Measured[Consciousness](value=Consciousness.A, source="measured"),
        ),
        medication_history_status="confirmed_list",
        medications=[
            MedicationEntry(
                raw_text="lisinopril 10mg",
                ingredients=[
                    IngredientStrength(
                        ingredient_id="lisinopril",
                        strength_amount=Decimal("10.0"),
                        strength_unit=DoseUnit.mg,
                    )
                ],
                last_dose_time=now,
                resolved=True,
            )
        ],
        allergy_history_status="confirmed_none",
        suspected_syndrome="chest_pain",
        chief_complaint_untrusted="Chest discomfort",
    )

    dumped_json = patient.model_dump_json()
    assert "84.7" in dumped_json
    assert "62.35" in dumped_json
    assert "36.75" in dumped_json
    assert "+00:00" in dumped_json or "Z" in dumped_json

    restored = Patient.model_validate_json(dumped_json)
    assert restored.age.value == Decimal("84.7")
    assert restored.weight_kg.value == Decimal("62.35")
    assert restored.vitals.temperature_c.value == Decimal("36.75")
    assert restored.assessed_at.tzinfo is not None
    assert restored.vitals.consciousness.value == Consciousness.A


def test_triage_response_full_round_trip() -> None:
    """TriageResponse round-trips cleanly through JSON with exact Decimals and verified steps."""
    data_dir = get_data_dir()
    registry = ClinicalRegistry.load_from_directory(data_dir)
    index = BM25ClinicalIndex(ingest_protocols(data_dir))

    now = datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)
    patient = Patient(
        assessed_at=now,
        age=Age(value=Decimal("45"), unit=AgeUnit.years),
        sex="male",
        pregnancy="not_applicable",
        weight_kg=Measured[Decimal](value=Decimal("84.7"), source="measured"),
        vitals=Vitals(
            systolic_bp_mmhg=Measured[int](value=85, source="measured"),
            heart_rate_bpm=Measured[int](value=115, source="measured"),
            respiratory_rate_bpm=Measured[int](value=24, source="measured"),
            spo2_percent=Measured[int](value=91, source="measured"),
            supplemental_o2=Measured[str](value="no", source="measured"),  # type: ignore[arg-type]
            temperature_c=Measured[Decimal](value=Decimal("37.1"), source="measured"),
            consciousness=Measured[Consciousness](value=Consciousness.A, source="measured"),
        ),
        medication_history_status="confirmed_none",
        allergy_history_status="confirmed_none",
        suspected_syndrome="anaphylaxis",
        chief_complaint_untrusted="Tongue swelling and dyspnea",
    )

    response = run_triage(
        patient=patient,
        registry=registry,
        index=index,
        llm=FakeLLM(FakeLLMProfile.COMPLIANT),
    )

    json_str = response.model_dump_json()
    assert "0.5" in json_str

    # Parse back into TriageResponse
    restored = TriageResponse.model_validate_json(json_str)
    assert restored.engine.verdict == response.engine.verdict
    assert len(restored.verified_steps) == len(response.verified_steps)
    if restored.verified_steps and restored.verified_steps[0].draft.requested_dose:
        assert isinstance(restored.verified_steps[0].draft.requested_dose.amount, Decimal)
        assert restored.verified_steps[0].draft.requested_dose.amount == Decimal("0.5")
